class AuditValidator:
    def validate(self, event):
        return all(
            [
                event.event_id,
                event.user_id,
                event.action,
                event.resource,
            ]
        )