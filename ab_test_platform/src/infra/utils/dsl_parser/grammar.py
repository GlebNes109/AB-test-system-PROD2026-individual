from lark import Lark

grammar = r"""
?start: expression

?expression: term (_OR term)*   -> or_
?term: factor (_AND factor)*    -> and_

?factor: _NOT factor            -> not_
       | comparison
       | "(" expression ")"

// comparison_in handles both IN and NOT IN (IN_OP carries the operator text)
comparison: FIELD OP value          -> comparison
          | FIELD IN_OP list_val    -> comparison_in

?value: NUMBER      -> number
      | STRING      -> string
      | BOOL        -> bool_val

list_val: "[" value ("," value)* "]"

FIELD: CNAME ("." CNAME)*

OP: ">=" | "<=" | "==" | "!=" | ">" | "<" | "="

// IN_OP priority 4 > _NOT priority 3 so "NOT IN" is lexed as a single token,
// not as _NOT followed by something
IN_OP.4: /NOT\s+IN/i | /IN/i

BOOL.4: /true/i | /false/i

_NOT.3: /NOT/i
_AND.3: /AND/i
_OR.3:  /OR/i

// single and double quoted strings
STRING: "'" /[^']*/ "'" | "\"" /[^\"]*/ "\""

%import common.CNAME
%import common.NUMBER
%import common.WS
%ignore WS
"""

parser = Lark(grammar, parser="lalr")
