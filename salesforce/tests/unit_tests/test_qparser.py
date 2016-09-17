from unittest import TestCase
from salesforce.backend.subselect import (
        find_closing_parenthesis, split_subquery, transform_except_subquery,
        mark_quoted_strings, subst_quoted_strings, simplify_expression,
        QQuery)
from salesforce.dbapi.mocksf import MockJsonResponse


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


class QQueryTest(TestCase):
    def test_parsed_aliases(self):
        """Verify that rroot_table is correctly removed from aliases"""
        sql = "SELECT LastName, Contact.FirstName, Contact.Account.Name, Account.Company FROM Contact"
        self.assertEqual(QQuery(sql).aliases, ['LastName', 'FirstName', 'Account.Name', 'Account.Company'])

    def test_aggregation(self):
        sql = "SELECT FirstName, COUNT(Id) xcount, COUNT(Phone) FROM Contact GROUP BY FirstName"
        self.assertEqual(QQuery(sql).aliases, ['FirstName', 'xcount', 'expr0'])

    def test_child_relationship(self):
        sql = "SELECT Company, (SELECT LastName FROM Contacts) FROM Account"
        self.assertEqual(QQuery(sql).aliases, ['Company', 'Contacts'])

    def test_parse_rest_response(self):
        sql = "SELECT Id, Account.Name FROM Contact LIMIT 1"
        mock_response = MockJsonResponse(  # inserted formating whitespace
            '{"totalSize":1, "done":true, "records":[{'
            '   "attributes":{"type":"Contact", "url":"/services/data/v37.0/sobjects/Contact/003A000000wJICkIAO"},'
            '   "Id":  "003A000000wJICkIAO",'
            '   "Account":{'
            '     "attributes":{"type": "Account", "url": "/services/data/v37.0/sobjects/Account/001A000000w1KuKIAU"},'
            '     "Name": "django-salesforce test"}}]}')
        mock_cursor = 'fake_any_non_empty_object'
        expected = [['003A000000wJICkIAO', 'django-salesforce test']]
        self.assertEqual(list(QQuery(sql).parse_rest_response(mock_response, mock_cursor)), expected)


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
