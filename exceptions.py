class ConnectionError(Exception):
    """Exception выбрасывается при ошибке подключения."""

    def __init__(self, message):
        """Перехватываем сообщение об ошибке."""
        self.message = message
        super().__init__(self.message)

    pass


class EndpointStatusError(Exception):
    """Exception выбрасывается при ошибке состояния сервера."""

    def __init__(self, message):
        """Перехватываем сообщение об ошибке."""
        self.message = message
        super().__init__(self.message)

    pass
