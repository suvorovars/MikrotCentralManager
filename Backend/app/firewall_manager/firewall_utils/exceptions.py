# app/firewall_manager/utils/exceptions.py

class FirewallError(Exception):
    """Базовое исключение firewall-логики"""
    pass


class FirewallConnectionError(FirewallError):
    """Ошибка подключения к MikroTik"""
    pass


class FirewallOperationError(FirewallError):
    """Ошибка выполнения операции в RouterOS"""
    pass


class AddressAlreadyExists(FirewallError):
    """Адрес уже существует в списке"""
    pass


class AddressNotFound(FirewallError):
    """Адрес не найден в списке"""
    pass
