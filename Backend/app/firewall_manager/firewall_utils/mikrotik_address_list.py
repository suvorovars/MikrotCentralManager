# app/firewall_manager/utils/mikrotik_address_list.py

from typing import List, Dict, Optional

from mikrotik_connector.connector import MikroTikConnector
from .exceptions import (
    FirewallConnectionError,
    FirewallOperationError,
    AddressAlreadyExists,
    AddressNotFound,
)


def _raise_connection_error(connector: MikroTikConnector, error: Exception) -> None:
    raise FirewallConnectionError(
        f"Failed to connect to MikroTik {connector.host}"
    ) from error


async def _fetch_address_entries(
    connector: MikroTikConnector,
    *,
    list_name: str,
    address: Optional[str] = None,
) -> List[Dict]:
    where = {"list": list_name}
    if address:
        where["address"] = address
    return await connector.ros_execute(
        path="/ip/firewall/address-list",
        action="print",
        where=where,
    )


async def get_address_list(connector: MikroTikConnector, list_name: str) -> List[Dict]:
    """
    Получить все записи address-list для указанного списка
    """
    try:
        return await _fetch_address_entries(connector, list_name=list_name)

    except Exception as e:
        if "No available API or SSH connection" in str(e):
            _raise_connection_error(connector, e)
        raise FirewallOperationError(
            f"Failed to fetch address-list '{list_name}'"
        ) from e


async def address_exists(connector: MikroTikConnector, list_name: str, address: str) -> bool:
    """
    Проверка существования адреса в списке
    """
    try:
        result = await _fetch_address_entries(
            connector,
            list_name=list_name,
            address=address,
        )
        return len(result) > 0

    except Exception as e:
        if "No available API or SSH connection" in str(e):
            _raise_connection_error(connector, e)
        raise FirewallOperationError(
            f"Failed to check address '{address}' in list '{list_name}'"
        ) from e


async def add_address(
    connector: MikroTikConnector,
    list_name: str,
    address: str,
    comment: Optional[str] = None,
) -> None:
    """
    Добавить адрес в address-list
    Идемпотентность обеспечивается через предварительную проверку
    """
    if await address_exists(connector, list_name, address):
        raise AddressAlreadyExists(
            f"Address '{address}' already exists in list '{list_name}'"
        )

    payload = {
        "list": list_name,
        "address": address,
    }

    if comment:
        payload["comment"] = comment

    try:
        await connector.ros_execute(
            path="/ip/firewall/address-list",
            action="add",
            params=payload,
        )

    except Exception as e:
        if "No available API or SSH connection" in str(e):
            _raise_connection_error(connector, e)
        raise FirewallOperationError(
            f"Failed to add address '{address}' to list '{list_name}'"
        ) from e


async def remove_address(
    connector: MikroTikConnector,
    list_name: str,
    address: str,
) -> None:
    """
    Удалить адрес из address-list
    """
    try:
        result = await _fetch_address_entries(
            connector,
            list_name=list_name,
            address=address,
        )
        if not result:
            raise AddressNotFound(
                f"Address '{address}' not found in list '{list_name}'"
            )

        for item in result:
            await connector.ros_execute(
                path="/ip/firewall/address-list",
                action="remove",
                params={".id": item[".id"]},
            )

    except Exception as e:
        if "No available API or SSH connection" in str(e):
            _raise_connection_error(connector, e)
        raise FirewallOperationError(
            f"Failed to remove address '{address}' from list '{list_name}'"
        ) from e
