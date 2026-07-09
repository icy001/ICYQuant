class ICYQuantException(Exception):
    pass


class OrderNotFoundError(ICYQuantException):
    pass


class RiskCheckFailedError(ICYQuantException):
    pass


class InsufficientFundsError(ICYQuantException):
    pass


class ReconciliationError(ICYQuantException):
    pass
