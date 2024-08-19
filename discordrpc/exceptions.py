class RPCException(Exception):
    def __init__(self, message: str = None):
        if message is None:
            message = 'An error has occurred within DiscordRPC'
        super().__init__(message)


class DiscordNotOpened(RPCException):
    def __init__(self):
        super().__init__("Error, could not find Discord. is Discord running?")


class InvalidID(RPCException):
    def __init__(self):
        super().__init__("Invalid ID, is the ID correct? Get Application ID on https://discord.com/developers/applications")
