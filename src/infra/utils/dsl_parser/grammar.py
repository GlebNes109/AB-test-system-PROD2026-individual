from lark import Lark

grammar = r"""
?start: expression

?expression: term (_OR term)*   -> or_
?term: factor (_AND factor)*    -> and_

?factor: _NOT factor            -> not_
       | comparison
       | "(" expression ")"

comparison: FIELD OP value

?value: NUMBER      -> number
      | STRING      -> string

FIELD: CNAME ("." CNAME)*


OP: ">" | ">=" | "<" | "<=" | "=" | "!="

_NOT.2: /NOT/i
_AND.2: /AND/i
_OR.2: /OR/i

STRING: "'" /[^']*/ "'"

%import common.CNAME
%import common.NUMBER
%import common.WS
%ignore WS
"""

parser = Lark(grammar, parser="lalr")



