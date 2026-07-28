class MessageTemplate:
    def build(self, alert):
        return (
            f"[{alert.severity}] "
            f"{alert.message}"
        )