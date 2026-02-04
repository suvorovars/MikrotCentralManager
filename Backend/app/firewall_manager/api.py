from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from device_manager.service import DeviceService
from security.auth import get_current_user
from firewall_manager.firewall_utils.exceptions import (
    FirewallConnectionError,
    FirewallOperationError,
    AddressAlreadyExists,
    AddressNotFound,
)
from firewall_manager.schemas import (
    FirewallListAddRequest,
    FirewallListRemoveRequest,
    FirewallListResponse,
    FirewallListOperationResponse,
    FirewallListType,
    FirewallGroupListResponse,
)
from firewall_manager.service import FirewallListService


router = APIRouter(
    prefix="/firewall/lists",
    tags=["firewall"],
    dependencies=[Depends(get_current_user)],
)


def _get_service(db: Session) -> FirewallListService:
    device_service = DeviceService(db)
    return FirewallListService(device_service)


def _raise_http_error(exc: Exception) -> None:
    if isinstance(exc, AddressAlreadyExists):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, AddressNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, FirewallConnectionError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, FirewallOperationError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    raise HTTPException(status_code=500, detail="Unexpected firewall error") from exc


@router.get(
    "/whitelist/{device_id}",
    response_model=FirewallListResponse,
)
async def get_whitelist(
    device_id: int,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.get_list(device_id, FirewallListType.whitelist)
    except Exception as exc:
        _raise_http_error(exc)


@router.get(
    "/whitelist/group/{group_id}",
    response_model=FirewallGroupListResponse,
)
async def get_whitelist_by_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.get_group_list(group_id, FirewallListType.whitelist)
    except Exception as exc:
        _raise_http_error(exc)


@router.get(
    "/blacklist/{device_id}",
    response_model=FirewallListResponse,
)
async def get_blacklist(
    device_id: int,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.get_list(device_id, FirewallListType.blacklist)
    except Exception as exc:
        _raise_http_error(exc)


@router.get(
    "/blacklist/group/{group_id}",
    response_model=FirewallGroupListResponse,
)
async def get_blacklist_by_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.get_group_list(group_id, FirewallListType.blacklist)
    except Exception as exc:
        _raise_http_error(exc)


@router.post(
    "/whitelist",
    response_model=FirewallListOperationResponse,
)
async def add_whitelist_entry(
    payload: FirewallListAddRequest,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.add_address(
            device_id=payload.device_id,
            list_type=FirewallListType.whitelist,
            address=payload.address,
            comment=payload.comment,
        )
    except Exception as exc:
        _raise_http_error(exc)


@router.post(
    "/blacklist",
    response_model=FirewallListOperationResponse,
)
async def add_blacklist_entry(
    payload: FirewallListAddRequest,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.add_address(
            device_id=payload.device_id,
            list_type=FirewallListType.blacklist,
            address=payload.address,
            comment=payload.comment,
        )
    except Exception as exc:
        _raise_http_error(exc)


@router.delete(
    "/whitelist",
    response_model=FirewallListOperationResponse,
)
async def remove_whitelist_entry(
    payload: FirewallListRemoveRequest,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.remove_address(
            device_id=payload.device_id,
            list_type=FirewallListType.whitelist,
            address=payload.address,
        )
    except Exception as exc:
        _raise_http_error(exc)


@router.delete(
    "/blacklist",
    response_model=FirewallListOperationResponse,
)
async def remove_blacklist_entry(
    payload: FirewallListRemoveRequest,
    db: Session = Depends(get_db),
):
    service = _get_service(db)
    try:
        return await service.remove_address(
            device_id=payload.device_id,
            list_type=FirewallListType.blacklist,
            address=payload.address,
        )
    except Exception as exc:
        _raise_http_error(exc)
