

def case_safe_id(id_15):
    """
    Convert a 15 char case-sensitive Id to 18 char case-insensitive Salesforce Id.

    Long  18 char Id are from SFDC API and from Apex. They are recommended by SF.
    Short 15 char Id are from SFDC formulas if omitted to use func CASESAFEID(),
    from reports or from parsed URLs in HTML.
    The long and short form are interchangable as the input to Salesforce API or
    to django-salesforce. They only need to be someway normalized if they are
    used as dictionary keys in a Python application code.
    """
    if id_15:
        suffix = []
        if len(id_15) == 15:
            for i in range(0, 15, 5):
                weight = 1
                digit = 0
                for ch in id_15[i:i + 5]:
                    if ch.isupper():
                        digit += weight
                    weight *= 2
                suffix.append(chr(ord('A') + digit) if digit < 26 else str(digit - 26))
        return id_15 + ''.join(suffix)
