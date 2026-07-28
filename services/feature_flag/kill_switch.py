class KillSwitchManager:

    def disable(self, feature):
        feature.enabled = False

        return feature
