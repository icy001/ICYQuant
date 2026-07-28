class NAVValidationEngine:
    def validate(self, nav):
        return {"valid": nav >= 0}
