class ServiceRegistry:
    def __init__(self):
        self.instances = {}

    def register(self, instance):
        self.instances[instance.instance_id] = instance

    def unregister(self, instance_id):
        self.instances.pop(instance_id, None)
