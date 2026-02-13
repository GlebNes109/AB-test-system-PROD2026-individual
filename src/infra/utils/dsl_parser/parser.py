from lark import UnexpectedInput

from src.infra.utils.dsl_parser.builder import ASTBuilder
from src.infra.utils.dsl_parser.exceptions import ParserError
from src.infra.utils.dsl_parser.grammar import parser
from src.infra.utils.dsl_parser.validation import ValidationContext, validate_rule
from src.infra.utils.dsl_parser.ast_nodes import Expr
from src.infra.utils.dsl_parser.dsl_schemas import DslValidateResponse, DslError


class DslParser:
    def validate(self, dsl_expression: str) -> DslValidateResponse:
        try:
            expr = self.parse(dsl_expression)
            validate_rule(expr, ValidationContext())
            normalized = expr.normalize()
            return DslValidateResponse(
                isValid=True,
                normalizedExpression=normalized,
                errors=[]
            )

        except UnexpectedInput as e:
            position = e.pos_in_stream

            near = None
            try:
                near = e.get_context(dsl_expression, span=3).splitlines()[0].strip()
            except Exception:
                pass
            return DslValidateResponse(
                isValid=False,
                normalizedExpression=None,
                errors=[
                    DslError(
                        code="DSL_PARSE_ERROR",
                        message="Синтаксическая ошибка в DSL выражении",
                        position=position,
                        near=near
                    )
                ]
            )

        except ParserError as e:
            return DslValidateResponse(
                isValid=False,
                normalizedExpression=None,
                errors=[
                    DslError(
                        code=e.code,
                        message=e.message,
                        position=None,
                        near=None
                    )
                ]
            )

        except Exception as e:
            return DslValidateResponse(
                isValid=False,
                normalizedExpression=None,
                errors=[
                    DslError(
                        code="DSL_PARSE_ERROR",
                        message=str(e),
                        position=None,
                        near=None
                    )
                ]
            )

    def parse(self, dsl_expression: str) -> Expr:
        tree = parser.parse(dsl_expression)
        return ASTBuilder().transform(tree)
