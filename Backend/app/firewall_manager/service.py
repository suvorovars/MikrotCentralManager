from typing import List, Optional

from mikrotik_connector import MikroTikConnector

from device_manager.service import DeviceService
from firewall_manager.firewall_utils import mikrotik_address_list
from firewall_manager.schemas import (
    FirewallListEntry,
    FirewallListResponse,
    FirewallListType,
    FirewallListOperationResponse,
)


LIST_NAMES = {
    FirewallListType.whitelist: "WhiteList",
    FirewallListType.blacklist: "BLAddress",
}

# Примечание: Deny_List используется для детекта сканеров (правила №9-10),
# а BlackList (BLAddress) — для блокировки трафика (правило №8).


class FirewallListService:
    def __init__(self, device_service: DeviceService):
        self.device_service = device_service

    def _get_list_name(self, list_type: FirewallListType) -> str:
        return LIST_NAMES[list_type]

    def _get_connector(self, device_id: int) -> MikroTikConnector:
        device_data = self.device_service.get_device_credentials(device_id)
        if not device_data:
            raise ValueError(f"Device {device_id} not found or credentials missing")

        return MikroTikConnector(
            host=device_data["host"],
            username=device_data["username"],
            password=device_data["password"],
            api_port=device_data["api_port"],
            ssh_port=device_data["ssh_port"],
            use_ssl=device_data["use_ssl"],
        )

    async def get_list(
        self,
        device_id: int,
        list_type: FirewallListType,
    ) -> FirewallListResponse:
        connector = self._get_connector(device_id)
        list_name = self._get_list_name(list_type)

        await connector.connect()
        try:
            raw_entries = await mikrotik_address_list.get_address_list(
                connector=connector,
                list_name=list_name,
            )
        finally:
            await connector.disconnect()

        entries = [
            FirewallListEntry(
                id=item.get(".id"),
                address=item.get("address"),
                list_name=item.get("list", list_name),
                comment=item.get("comment"),
                disabled=item.get("disabled"),
            )
            for item in raw_entries
        ]

        return FirewallListResponse(
            device_id=device_id,
            list_type=list_type,
            list_name=list_name,
            entries=entries,
        )

    async def add_address(
        self,
        device_id: int,
        list_type: FirewallListType,
        address: str,
        comment: Optional[str],
    ) -> FirewallListOperationResponse:
        connector = self._get_connector(device_id)
        list_name = self._get_list_name(list_type)

        await connector.connect()
        try:
            await mikrotik_address_list.add_address(
                connector=connector,
                list_name=list_name,
                address=address,
                comment=comment,
            )
        finally:
            await connector.disconnect()

        return FirewallListOperationResponse(
            device_id=device_id,
            list_type=list_type,
            list_name=list_name,
            address=address,
            status="added",
        )

    async def remove_address(
        self,
        device_id: int,
        list_type: FirewallListType,
        address: str,
    ) -> FirewallListOperationResponse:
        connector = self._get_connector(device_id)
        list_name = self._get_list_name(list_type)

        await connector.connect()
        try:
            await mikrotik_address_list.remove_address(
                connector=connector,
                list_name=list_name,
                address=address,
            )
        finally:
            await connector.disconnect()

        return FirewallListOperationResponse(
            device_id=device_id,
            list_type=list_type,
            list_name=list_name,
            address=address,
            status="removed",
        )
