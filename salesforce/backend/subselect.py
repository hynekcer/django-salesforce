"""Parse SOQL, including subqueries

Subqueries are (fortunately for the implementation) very restricted by
[Force.com SOQL]
(https://resources.docs.salesforce.com/sfdc/pdf/salesforce_soql_sosl.pdf)
- "only root queries support aggregate expressions"
- Subqueries can not be in "OR" condition, because it is an additional level.

These expressions can be supported here, but currently unimplemented:
    FORMAT(), convertCurrency(), toLabel(),
    Date Functions..., convertTimezone() in Date Functions
    DISTANCE(x, GEOLOCATION(...))
Especially DISTANCE and GEOLOCATION are not trivial because they would
require a combined parser for parentheses and commas.

Unsupported GROUP BY ROLLUP and GROUP BY CUBE
"""
import re
from unittest import TestCase
from salesforce.dbapi.driver import ProgrammingError

# reserved wods can not be used as alias names
RESERVED_WORDS = set((
    'AND, ASC, DESC, EXCLUDES, FIRST, FROM, GROUP, HAVING, '
    'IN, INCLUDES, LAST, LIKE, LIMIT, NOT, NULL, NULLS, '
    'OR, SELECT, WHERE, WITH'
).split(', '))
AGGREGATION_WORDS = set((
    'AVG, COUNT, COUNT_DISTINCT, MIN, MAX, SUM'
).split(', '))
pattern_aggregation = re.compile(r'\b(?:{})(?=\()'.format('|'.join(AGGREGATION_WORDS)), re.I)
pattern_groupby = re.compile(r'\bGROUP BY\b', re.I)


class QQuery(object):
    """Parse the SOQL query to an object that helps to correctly interpret the response

    parse_rest_response:  parse the response
    """
    # type of query: QRootQuery, QFieldSubquery, QWhereSubquery
    # type of field: QField, QAggregation, QFieldSubquery

    def __init__(self, soql=None):
        self.soql = None
        self.fields = []
        self.aliases = []
        self.root_table = None
        # is_aggregation: only to know if aliases are relevant for output
        self.is_aggregation = False
        self.is_count_query = False
        self.has_child_rel_field = False
        # extra_soql: everything what is after the root table name (and
        # after optional alias), usually WHERE...
        self.extra_soql = None
        self.subqueries = None
        if soql:
            self._from_sql(soql)

    def _from_sql(self, soql):
        """Create Force.com SOQL tree structure from SOQL"""
        assert not self.soql, "Don't use _from_sql method directly"
        self.soql = soql
        soql, self.subqueries = split_subquery(soql)
        match_parse = re.match(r'SELECT (.*) FROM (\w+)\b(.*)$', soql, re.I)
        if not match_parse:
            raise ProgrammingError('Invalid SQL: %s' % self.soql)
        fields_sql, self.root_table, self.extra_soql = match_parse.groups()
        fields = [x.strip() for x in fields_sql.split(',')]
        self.is_aggregation = bool(pattern_groupby.search(self.extra_soql) or
                                   pattern_aggregation.search(fields[0]))
        self.is_plain_count = fields[0].upper == 'COUNT()'
        consumed_subqueries = 0
        expr_alias_counter = 0
        #
        # import pdb; pdb.set_trace()
        if not self.is_plain_count:
            for field in fields:
                if self.is_aggregation:
                    match = re.search(r'\b\w+$', field)
                    if match:
                        alias = match.group()
                        assert alias not in RESERVED_WORDS
                        if match.start() > 0 and field[match.start() - 1] == ' ':
                            field = field[match.start() - 1]
                    else:
                        alias = 'expr{}'.format(expr_alias_counter)
                        expr_alias_counter += 1
                    assert '&' not in field, "Subquery not expected as field in aggregation query"
                elif '&' in field:
                    assert field == '(&)'
                    subquery = QQuery(self.subqueries[consumed_subqueries][0])
                    consumed_subqueries += 1
                    self.has_child_rel_field = True
                    field = subquery
                    alias = subquery.root_table
                else:
                    alias = field
                    if '.' in alias and alias.split('.', 1)[0].lower() == self.root_table.lower():
                        alias = alias.split('.', 1)[1]
                self.aliases.append(alias)
                self.fields.append(field)
        # TODO it is not currently necessary to parse the exta_soql
        pass

    @staticmethod
    def _make_flat(row_dict, cursor=None):
        """Replace nested objects by flat "object.object.name" flat structure"""
        out = {}
        for k, v in row_dict.items():
            if (not isinstance(v, dict) or (
                'done' in v and 'records' in v and 'totalSize' in v
            )):
                out[k.lower()] = v
            else:
                for sub_k, sub_v in QQuery._make_flat(v, cursor).items():
                    out[k.lower() + '.' + sub_k] = sub_v
        return out

    def parse_rest_response(self, response, cursor=None):
        """Parse the REST API response to DB API cursor flat response"""
        resp = response.json()
        if self.is_plain_count:
            # result of "SELECT COUNT() FROM ... WHERE ..."
            assert resp['records'] == []
            yield resp['totalSize']
        else:
            while True:
                for row_deep in resp['records']:
                    assert self.is_aggregation == (row_deep['attributes']['type'] == 'AggregateResult')
                    row_flat = self._make_flat(row_deep, cursor)
                    assert all(not isinstance(x, dict) or x['done'] for x in row_flat)
                    yield [row_flat[k.lower()] for k, v in zip(self.aliases, self.fields)]
                if not resp['done']:
                    if not cursor:
                        raise ProgrammingError("Must get a cursor")
                    resp = cursor.query_more(response['nextRecordsUrl']).json()
                else:
                    break


def mark_quoted_strings(sql):
    """Mark all quoted strings in the SOQL by '@' and get them as params,
    with respect to all escaped backslashes and quotes.
    """
    pm_pattern = re.compile(r"'[^\\']*(?:\\[\\'][^\\']*)*'")
    bs_pattern = re.compile(r"\\([\\'])")
    out_pattern = re.compile("^(?:[-!()*+,.:<=>\w\s|%s])*$")
    start = 0
    out = []
    params = []
    for match in pm_pattern.finditer(sql):
        out.append(sql[start:match.start()])
        assert out_pattern.match(sql[start:match.start()])
        params.append(bs_pattern.sub('\\1', sql[match.start() + 1:match.end() - 1]))
        start = match.end()
    out.append(sql[start:])
    assert out_pattern.match(sql[start:])
    return '@'.join(out), params


def subst_quoted_strings(sql, params):
    """Reverse operation to mark_quoted_strings - substitutes '@' by params.
    """
    parts = sql.split('@')
    assert len(parts) == len(params) + 1
    out = []
    for i, param in enumerate(params):
        out.append(parts[i])
        out.append("'%s'" % param.replace('\\', '\\\\').replace("\'", "\\\'"))
    out.append(parts[-1])
    return ''.join(out)


def find_closing_parenthesis(sql, startpos):
    """Find the pair of opening and closing parentheses.

    Starts search at the position startpos.
    Returns tuple of positions (opening, closing) if search succeeds, otherwise None.
    """
    pattern = re.compile(r'[()]')
    level = 0
    opening = []
    for match in pattern.finditer(sql, startpos):
        par = match.group()
        if par == '(':
            if level == 0:
                opening = match.start()
            level += 1
        if par == ')':
            assert level > 0
            level -= 1
            if level == 0:
                closing = match.end()
                return opening, closing


def transform_except_subquery(sql, func):
    """Call a func on every part of SOQL query except nested (SELECT ...)"""
    start = 0
    out = []
    while sql.find('(SELECT', start) > -1:
        pos = sql.find('(SELECT', start)
        out.append(func(sql[start:pos]))
        start, pos = find_closing_parenthesis(sql, pos)
        out.append(sql[start:pos])
        start = pos
    out.append(func(sql[start:len(sql)]))
    return ''.join(out)


def split_subquery(sql):
    """Split on subqueries and replace them by '&'."""
    sql, params = mark_quoted_strings(sql)
    sql = simplify_expression(sql)
    _ = params  # NOQA
    start = 0
    out = []
    subqueries = []
    pattern = re.compile(r'\(SELECT\b', re.I)
    match = pattern.search(sql, start)
    while match:
        out.append(sql[start:match.start() + 1] + '&')
        start, pos = find_closing_parenthesis(sql, match.start())
        start, pos = start + 1, pos - 1
        subqueries.append(split_subquery(sql[start:pos]))
        start = pos
        match = pattern.search(sql, start)
    out.append(sql[start:len(sql)])
    return ''.join(out), subqueries


def simplify_expression(txt):
    """Remove all unecessary whitespace and some very usual space"""
    minimal = re.sub(r'\s', ' ',
                     re.sub(r'\s(?=\W)', '',
                            re.sub(r'(?<=\W)\s', '',
                                   txt.strip())))
    # add space before some "(" and after some ")"
    return re.sub(r'\)(?=\w)', ') ',
                  re.sub(r'(,|\b(?:{}))\('.format('|'.join(RESERVED_WORDS)), '\\1 (',
                         minimal))


class TestSubSelectSearch(TestCase):
    def test_parenthesis(self):
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 0), (0, 2))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 2), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 3), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 6), (7, 11))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 13), (13, 15))
        self.assertRaises(AssertionError, find_closing_parenthesis, '() (() (())) ()', 1)

    def test_subquery(self):
        def func(x):
            return '*transfomed*'
        sql = "SELECT a, (SELECT x FROM y) FROM b WHERE (c IN (SELECT p FROM q WHERE r = %s) AND c = %s)"
        expected = "*transfomed*(SELECT x FROM y)*transfomed*(SELECT p FROM q WHERE r = %s)*transfomed*"
        self.assertEqual(transform_except_subquery(sql, func), expected)

    def test_split_subquery(self):
        sql = " SELECT a, ( SELECT x FROM y) FROM b WHERE (c IN (SELECT p FROM q WHERE r = %s) AND c = %s)"
        expected = ("SELECT a, (&) FROM b WHERE (c IN (&) AND c=%s)",
                    [("SELECT x FROM y", []),
                     ("SELECT p FROM q WHERE r=%s", [])
                     ])
        self.assertEqual(split_subquery(sql), expected)

    def test_nested_subquery(self):
        def func(x):
            return '*transfomed*'
        sql = "SELECT a, (SELECT x, (SELECT p FROM q) FROM y) FROM b"
        expected = "*transfomed*(SELECT x, (SELECT p FROM q) FROM y)*transfomed*"
        self.assertEqual(transform_except_subquery(sql, func), expected)

    def test_split_nested_subquery(self):
        sql = "SELECT a, (SELECT x, (SELECT p FROM q) FROM y) FROM b"
        expected = ("SELECT a, (&) FROM b",
                    [("SELECT x, (&) FROM y",
                      [("SELECT p FROM q", [])]
                      )]
                    )
        self.assertEqual(split_subquery(sql), expected)


class ReplaceQuotedStringsTest(TestCase):

    def test_subst_quoted_strings(self):
        def inner(sql, expected):
            result = mark_quoted_strings(sql)
            self.assertEqual(result, expected)
            self.assertEqual(subst_quoted_strings(*result), sql)
        inner("where x=''", ("where x=@", ['']))
        inner("a'bc'd", ("a@d", ['bc']))
        inner(r"a'bc\\'d", ("a@d", ['bc\\']))
        inner(r"a'\'\\'b''''", ("a@b@@", ['\'\\', '', '']))
        self.assertRaises(AssertionError, mark_quoted_strings, r"a'bc'\\d")
        self.assertRaises(AssertionError, mark_quoted_strings, "a'bc''d")

    def test_simplify_expression(self):
        self.assertEqual(simplify_expression(' a \t b  c . . d '), 'a b c..d')
