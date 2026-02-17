from lark import UnexpectedInput

from src.domain.interfaces.dsl_parser import DslParserInterface
from src.infra.utils.dsl_parser.builder import ASTBuilder
from src.infra.utils.dsl_parser.grammar import parser
from src.infra.utils.dsl_parser.validation import ValidationContext, validate_rule
from src.infra.utils.dsl_parser.ast_nodes import Expr
from src.infra.utils.dsl_parser.exceptions import ParserError


class DslParser(DslParserInterface):
    def validate(self, dsl_expression: str) -> bool:
        if not dsl_expression:
            return True
        try:
            expr = self._parse(dsl_expression)
            validate_rule(expr, ValidationContext())
            return True
        except (UnexpectedInput, ParserError, ValueError):
            return False

    def _parse(self, dsl_expression: str) -> Expr:
        tree = parser.parse(dsl_expression)
        return ASTBuilder().transform(tree)

    def check_rule_matches(self, context: dict, dsl_expr: str | None) -> bool:
        # нет правила = все пользователи проходят
        if not dsl_expr:
            return True
        try:
            expr = self._parse(dsl_expr)
            return expr.eval(context)
        except (UnexpectedInput, ParserError, ValueError):
            return False