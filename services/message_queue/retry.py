class RetryManager:

    def retry(
        self,
        message
    ):
        message.status = "RETRY"

        return message
