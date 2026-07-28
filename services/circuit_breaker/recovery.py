class RecoveryController:
    def recover(self, machine):
        machine.half_open()
        return machine.current()
