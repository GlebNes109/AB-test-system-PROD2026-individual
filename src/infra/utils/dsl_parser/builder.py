from lark import Transformer

from src.infra.utils.dsl_parser.ast_nodes import And, Or, Not, Comparison


class ASTBuilder(Transformer):
    def or_(self, items):
        if len(items) == 1:
            return items[0]
        return Or(items)

    def and_(self, items):
        if len(items) == 1:
            return items[0]
        return And(items)

    def not_(self, items):
        return Not(items[0])

    def comparison(self, items):
        field, op, value = items
        return Comparison(field, op, value)

    def number(self, items):
        raw = items[0]
        text = str(raw)
        if "." in str(raw):
            return float(text)
        return int(text)

    def string(self, items):
        return items[0][1:-1]

    def FIELD(self, token):
        return token.value

    def OP(self, token):
        return token.value



