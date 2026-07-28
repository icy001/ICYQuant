class IncidentManager:

    def create(self, alert):
        return {
            "incident_id": f"INC-{alert.alert_id}",
            "level": alert.level,
            "status": "OPEN"
        }
