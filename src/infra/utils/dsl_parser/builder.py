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

    def comparison_in(self, items):
        field, in_op, list_val = items
        # normalize "NOT  IN" -> "NOT IN", "in" -> "IN"
        op = " ".join(str(in_op).upper().split())
        return Comparison(field, op, list_val)

    def list_val(self, items):
        return list(items)

    def number(self, items):
        raw = items[0]
        text = str(raw)
        if "." in text:
            return float(text)
        return int(text)

    def string(self, items):
        # strip surrounding quotes (single or double)
        return str(items[0])[1:-1]

    def bool_val(self, items):
        return str(items[0]).lower() == "true"

    def FIELD(self, token):
        return token.value

    def OP(self, token):
        return token.value