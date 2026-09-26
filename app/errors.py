from app.wire import ErrorCode


class JobFailed(Exception):
    """A job that ends in a `failed` callback. `code` is the stable value
    Laravel stores in ai_jobs.error_code (its check constraint requires one), and
    is always a member of `app.wire.ErrorCode` — openapi.yaml's enum is checked
    against that list, so a new failure path cannot invent a code the contract
    does not declare. The message is for logs, not for users."""

    def __init__(self, message: str, code: ErrorCode):
        super().__init__(message)
        self.code = code
