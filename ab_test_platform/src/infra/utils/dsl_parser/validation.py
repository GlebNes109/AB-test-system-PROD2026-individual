class ValidationContext:
    def __init__(self):
        # поля не ограничены — контекст пользователя открытый
        self.allow_and = True
        self.allow_or = True
        self.allow_not = True


def validate_rule(expr, ctx: ValidationContext):
    expr.validate(ctx)