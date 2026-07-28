class FailureDetector:
    def detect(self, failure_record, config):
        return failure_record.error_count >= config.failure_threshold
