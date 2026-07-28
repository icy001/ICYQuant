class CommandHandler:
    def handle(self, command):
        return {
            "status": "ACCEPTED",
            "command": command.command_id
        }
