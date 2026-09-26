class JobFailed(Exception):
    """A job that ends in a `failed` callback. `code` is the stable value
    Laravel stores in ai_jobs.error_code (its check constraint requires one);
    the message is for logs, not for users."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code
