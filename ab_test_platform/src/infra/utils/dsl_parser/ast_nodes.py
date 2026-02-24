from typing import Any

from ab_test_platform.src.infra.utils.dsl_parser.exceptions import ParserError


def base_normalize(parent, child):
    s = child.normalize()
    if child.priority < parent.priority:
        return f"({s})"
    return s


class Expr:
    priority = 0

    def eval(self, tx: dict) -> bool:
        raise NotImplementedError

    def validate(self, ctx) -> None:
        raise NotImplementedError

    def normalize(self) -> str:
        raise NotImplementedError

    def count_nodes(self) -> int:
        raise NotImplementedError


class And(Expr):
    priority = 2

    def __init__(self, items):
        self.items = items

    def eval(self, tx):
        return all(expr.eval(tx) for expr in self.items)

    def validate(self, ctx):
        if not ctx.allow_and:
            raise ValueError("AND not supported")
        for e in self.items:
            e.validate(ctx)

    def normalize(self):
        return " AND ".join(base_normalize(self, e) for e in self.items)

    def count_nodes(self):
        return 1 + sum(e.count_nodes() for e in self.items)


class Or(Expr):
    priority = 1

    def __init__(self, items):
        self.items = items

    def eval(self, tx):
        return any(expr.eval(tx) for expr in self.items)

    def validate(self, ctx):
        if not ctx.allow_or:
            raise ValueError("OR not supported")
        for e in self.items:
            e.validate(ctx)

    def normalize(self):
        return " OR ".join(base_normalize(self, e) for e in self.items)

    def count_nodes(self):
        return 1 + sum(e.count_nodes() for e in self.items)


class Not(Expr):
    priority = 3

    def __init__(self, expr):
        self.expr = expr

    def eval(self, tx):
        return not self.expr.eval(tx)

    def validate(self, ctx):
        if not ctx.allow_not:
            raise ValueError("NOT not supported")
        self.expr.validate(ctx)

    def normalize(self):
        inner = base_normalize(self, self.expr)
        return f"NOT {inner}"

    def count_nodes(self):
        return 1 + self.expr.count_nodes()


class Comparison(Expr):
    priority = 4

    def __init__(self, field: str, op: str, value: Any):
        self.field = field
        self.op = op
        self.value = value

    def eval(self, tx):
        v = tx
        for part in self.field.split("."):
            if not isinstance(v, dict) or part not in v:
                # отсутствующий атрибут = false
                return False
            v = v[part]

        if v is None:
            return False

        if self.op in ("=", "=="):
            return v == self.value
        if self.op == "!=":
            return v != self.value
        if self.op == ">":
            return v > self.value
        if self.op == ">=":
            return v >= self.value
        if self.op == "<":
            return v < self.value
        if self.op == "<=":
            return v <= self.value
        if self.op == "IN":
            return v in self.value
        if self.op == "NOT IN":
            return v not in self.value

        raise ValueError(f"Unknown operator {self.op}")

    def validate(self, ctx):
        # поля не ограничены — контекст пользователя открытый (любые props)
        all_ops = {">", ">=", "<", "<=", "=", "==", "!=", "IN", "NOT IN"}
        if self.op not in all_ops:
            raise ParserError(code="DSL_INVALID_OPERATOR", message="неизвестный оператор")

    def normalize(self):
        return f"{self.field} {self.op} {repr(self.value)}"

    def count_nodes(self):
        return 1
