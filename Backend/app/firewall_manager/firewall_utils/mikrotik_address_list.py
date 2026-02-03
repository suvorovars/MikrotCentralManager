# app/firewall_manager/utils/mikrotik_address_list.py

from typing import List, Dict, Optional

from librouteros.exceptions import LibRouterosError

from mikrotik_connector.connector import MikroTikConnector
from .exceptions import (
    FirewallConnectionError,
    FirewallOperationError,
    AddressAlreadyExists,
    AddressNotFound,
)


def _get_api(connector: MikroTikConnector):
    try:
        return connector.get_api()
    except Exception as e:
        raise FirewallConnectionError(
            f"Failed to connect to MikroTik {connector.host}"
        ) from e


def get_address_list(connector: MikroTikConnector, list_name: str) -> List[Dict]:
    """
    Получить все записи address-list для указанного списка
    """
    api = _get_api(connector)

    try:
        result = api(
            "/ip/firewall/address-list/print",
            where={"list": list_name},
        )
        return list(result)

    except LibRouterosError as e:
        raise FirewallOperationError(
            f"Failed to fetch address-list '{list_name}'"
        ) from e


def address_exists(connector: MikroTikConnector, list_name: str, address: str) -> bool:
    """
    Проверка существования адреса в списке
    """
    api = _get_api(connector)

    try:
        result = api(
            "/ip/firewall/address-list/print",
            where={
                "list": list_name,
                "address": address,
            },
        )
        return len(list(result)) > 0

    except LibRouterosError as e:
        raise FirewallOperationError(
            f"Failed to check address '{address}' in list '{list_name}'"
        ) from e


def add_address(connector: MikroTikConnector, list_name: str, address: str, comment: Optional[str] = None) -> None:
    """
    Добавить адрес в address-list
    Идемпотентность обеспечивается через предварительную проверку
    """
    if address_exists(connector, list_name, address):
        raise AddressAlreadyExists(
            f"Address '{address}' already exists in list '{list_name}'"
        )

    api = _get_api(connector)

    payload = {
        "list": list_name,
        "address": address,
    }

    if comment:
        payload["comment"] = comment

    try:
        api("/ip/firewall/address-list/add", **payload)

    except LibRouterosError as e:
        raise FirewallOperationError(
            f"Failed to add address '{address}' to list '{list_name}'"
        ) from e


def remove_address(connector: MikroTikConnector, list_name: str, address: str) -> None:
    """
    Удалить адрес из address-list
    """
    api = _get_api(connector)

    try:
        result = list(
            api(
                "/ip/firewall/address-list/print",
                where={
                    "list": list_name,
                    "address": address,
                },
            )
        )

        if not result:
            raise AddressNotFound(
                f"Address '{address}' not found in list '{list_name}'"
            )

        for item in result:
            api(
                "/ip/firewall/address-list/remove",
                **{".id": item[".id"]},
            )

    except LibRouterosError as e:
        raise FirewallOperationError(
            f"Failed to remove address '{address}' from list '{list_name}'"
        ) from e
