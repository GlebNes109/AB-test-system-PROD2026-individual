from abc import abstractmethod
from typing import Protocol

class DslParserInterface(Protocol):
    @abstractmethod
    def validate(self, dsl_expression: str) -> bool:
        ...

    @abstractmethod
    def check_rule_matches(self, data, dsl_expr) -> bool:
        ...