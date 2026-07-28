class RetryManager:
    def retry(self, task):
        task.status = "RETRY"
        return task
