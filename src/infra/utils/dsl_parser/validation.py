class ValidationContext:
    def __init__(self):
        self.allowed_fields = {
            "amount",
            "currency",
            "merchantId",
            "ipAddress",
            "deviceId",
            "user.age",
            "user.region",
        }

        self.numeric_ops = {">", ">=", "<", "<=", "=", "!="}
        self.string_ops = {"=", "!="}

        self.allow_and = True
        self.allow_or = True
        self.allow_not = True


def validate_rule(expr, ctx: ValidationContext):
    """if expr.count_nodes() > 100:
        raise DslError(code="DSL_TOO_COMPLEX", )"""
    expr.validate(ctx)



