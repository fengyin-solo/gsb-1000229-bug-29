"""气象监测接口：维护气象数据，覆盖发布预警、升级预警、解除预警等动作。

所有接口通过 X-Account 请求头识别账号，并把可见范围交给共享目录统一裁定，
列表、详情、值班看板因此始终是同一口径。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.weather import WeatherService
from app.sharing import share_catalog

router = APIRouter(prefix="/api/weather", tags=["气象监测"])

service = WeatherService()

LIST_FIELDS = ["站点编号", "辐照度", "风速", "风向", "气温", "湿度", "降雨量", "记录时间"]
STATUSES = ["正常", "大风预警", "暴雨预警", "冰雹预警"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按站点编号检索"),
    status: str | None = Query(default=None, description="正常、大风预警、暴雨预警、冰雹预警"),
    page: int = 1,
    size: int = 20,
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> PageResult[dict]:
    """按站点编号与状态过滤气象监测列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    account = share_catalog.account(x_account)
    items, total = service.list_entries(
        account, keyword=keyword, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/board", response_model=dict)
def weather_board(
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> dict[str, Any]:
    """值班看板：气象监测口径，与列表、详情共用同一个共享目录。"""
    account = share_catalog.account(x_account)
    items = service.dashboard_rows(account)
    warnings = sum(1 for row in items if row.get("status") != "正常")
    return {"module": "weather", "total": len(items), "warnings": warnings, "items": items}


@router.get("/export")
def export_entries(
    x_account: str | None = Header(default=None, alias="X-Account"),
    account: str | None = Query(default=None, description="导出链接携带的账号 key（window.open 无法带请求头）"),
) -> dict[str, Any]:
    """导出气象监测清单：返回当前账号可见范围内的全量数据。"""
    viewer = share_catalog.account(x_account or account)
    items, total = service.list_entries(viewer, page=1, size=10000)
    return {"module": "weather", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int,
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> dict:
    """读取单条气象数据明细；不存在或不可见时给出可读的错误说明。"""
    account = share_catalog.account(x_account)
    entry = service.get_entry(account, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"气象数据 {entry_id} 不存在或无权查看")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(
    payload: EntryPayload,
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> ActionResult:
    """登记一条气象数据，缺字段时说明原因而不是静默丢弃。"""
    account = share_catalog.account(x_account)
    entry, missing = service.create_entry(account, payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message="当前账号（外协）无权登记气象数据")
    return ActionResult(ok=True, message="气象数据已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> ActionResult:
    """对单条气象数据执行发布预警、升级预警、解除预警；不允许的动作会被拦下并说明原因。"""
    account = share_catalog.account(x_account)
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(account, entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/share", response_model=ActionResult)
def share_entry(
    entry_id: int,
    payload: EntryPayload,
    x_account: str | None = Header(default=None, alias="X-Account"),
) -> ActionResult:
    """归属站点维护共享对象：站点编号列表，或「外协」。"""
    account = share_catalog.account(x_account)
    raw = payload.values.get("scopes") or []
    scopes = [str(item) for item in raw] if isinstance(raw, list) else [str(raw)]
    entry, message = service.share(account, entry_id, scopes)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
