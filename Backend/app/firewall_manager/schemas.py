from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class FirewallListType(str, Enum):
    whitelist = "whitelist"
    blacklist = "blacklist"


class FirewallListEntry(BaseModel):
    id: Optional[str] = None
    address: str
    list_name: str
    comment: Optional[str] = None
    disabled: Optional[bool] = None


class FirewallListResponse(BaseModel):
    device_id: int
    list_type: FirewallListType
    list_name: str
    entries: List[FirewallListEntry]


class FirewallListAddRequest(BaseModel):
    device_id: int = Field(..., ge=1)
    address: str = Field(..., min_length=1)
    comment: Optional[str] = None


class FirewallListRemoveRequest(BaseModel):
    device_id: int = Field(..., ge=1)
    address: str = Field(..., min_length=1)


class FirewallListOperationResponse(BaseModel):
    device_id: int
    list_type: FirewallListType
    list_name: str
    address: str
    status: str


class FirewallGroupListResponse(BaseModel):
    group_id: int
    group_name: str
    list_type: FirewallListType
    list_name: str
    devices: List[FirewallListResponse]
