"""气象监测业务规则：状态流转、字段校验与筛选口径都收在这里。

可见范围统一走 app.sharing 的共享目录，列表 / 详情 / 值班看板不得各自过滤；
写动作只更新状态字段，owner 与共享来源（共享目录授权）始终保留，不被提交覆盖。
"""
from __future__ import annotations

from typing import Any

from app.sharing import (
    OWNER_FIELD,
    Account,
    VENDOR_SCOPE,
    share_catalog,
)
from app.store import store

MODULE = "weather"
REQUIRED_FIELDS = ["站点编号", "辐照度", "风速"]
STATUS_ORDER = ["正常", "大风预警", "暴雨预警", "冰雹预警"]
ACTION_RULES = {"发布预警": "大风预警", "升级预警": "暴雨预警", "解除预警": "正常"}
NEGATIVE_ACTIONS = []


class WeatherService:
    def list_entries(
        self,
        account: Account,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # 第一步永远是共享目录可见性过滤，关键字/状态只能在可见集合内收窄
        rows = share_catalog.visible_rows(account, store.rows(MODULE))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("站点编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [share_catalog.project(account, row) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, account: Account, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None or not share_catalog.can_view(account, entry):
            return None
        return share_catalog.project(account, entry)

    def dashboard_rows(self, account: Account) -> list[dict[str, Any]]:
        """值班看板取数：与列表、详情同一个共享目录口径。"""
        rows = share_catalog.visible_rows(account, store.rows(MODULE))
        return [share_catalog.project(account, row) for row in rows]

    def create_entry(
        self, account: Account, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        # 外协账号不允许登记气象数据：共享目录只授予其只读可见
        if account.is_vendor:
            return None, []
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        # 归属站点：站点账号只能挂在自己站点；管理员可显式指定
        owner = account.station or str(values.get("站点编号", "")).strip()
        entry[OWNER_FIELD] = owner
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return share_catalog.project(account, entry), []

    def run_action(
        self, account: Account, entry_id: int, action: str
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"气象数据 {entry_id} 不存在或已归档"
        if not share_catalog.can_view(account, entry):
            # 不可见即按不存在处理，避免通过动作接口探测他站数据
            return None, f"气象数据 {entry_id} 不存在或已归档"
        if not share_catalog.can_write(account, entry):
            return None, "当前账号为只读共享（外协），无权对该气象数据执行操作"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于气象监测可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 只改状态相关字段；owner / 站点编号 / 共享授权原样保留，杜绝来源被覆盖
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return share_catalog.project(account, entry), f"气象数据已{action}"

    def share(
        self, account: Account, entry_id: int, scopes: list[str]
    ) -> tuple[dict[str, Any] | None, str]:
        """归属站点把自己的记录共享给其他站点或外协；非归属方无权共享。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"气象数据 {entry_id} 不存在或已归档"
        if not share_catalog.is_owner(account, entry):
            return None, "只有记录归属站点可以维护共享范围"
        targets = [scope.strip() for scope in scopes if scope.strip()]
        if not targets:
            return None, "共享对象不能为空"
        normalized = [VENDOR_SCOPE if scope == "外协" else scope for scope in targets]
        grant = share_catalog.grant(entry_id, normalized, source=str(entry.get(OWNER_FIELD, "")))
        view = share_catalog.project(account, entry)
        return view, f"已共享给：{'、'.join(grant.scopes)}"
