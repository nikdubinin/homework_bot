class ConnectionError(Exception):
    """Exception выбрасывается при ошибке подключения."""

    pass


class EndpointStatusError(Exception):
    """Exception выбрасывается при ошибке состояния сервера."""

    pass
