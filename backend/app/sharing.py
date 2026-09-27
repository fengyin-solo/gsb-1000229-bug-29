"""共享目录：气象数据可见范围与共享来源的唯一口径。

列表、详情、值班看板三个入口都必须经过这里取数，禁止各自维护一套过滤逻辑，
否则会出现列表看得到、看板看不到（或反过来）的口径漂移。

账号模型（演示用，真实项目换成登录态/权限中心）：
- admin   值班管理员：本站点全权，可读全部共享数据，可对任意可见记录执行动作。
- station 站点账号：只能看本站点记录 + 明确共享给本站点的记录；
           非本站点的共享记录按字段屏蔽敏感气象项（如风速）。
- vendor  外协账号：只能看明确共享给外协的记录，且默认只读；
           越权提交（写他站/未共享记录）一律拒绝。

共享关系（shares）以原记录为锚点，动作执行只改状态字段，
不覆盖 owner / 共享来源 / 原记录归属，避免“共享来源和原记录被覆盖”。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 站点账号只看本站点；用站点编号前缀之外的归属字段判定，避免字符串误匹配
OWNER_FIELD = "owner"
SOURCE_FIELD = "共享来源"
ORIGIN_FIELD = "原记录"
SHARED_WITH_FIELD = "共享给"

# 非归属站点通过共享目录看到记录时，需要屏蔽的敏感气象字段
SENSITIVE_FIELDS = ("风速",)
MASK = "***"


@dataclass(frozen=True)
class Account:
    key: str
    name: str
    kind: str  # admin / station / vendor
    station: str = ""  # 站点账号绑定的站点编号

    @property
    def is_admin(self) -> bool:
        return self.kind == "admin"

    @property
    def is_vendor(self) -> bool:
        return self.kind == "vendor"


# 三个演示账号：请求头 X-Account 传 key；缺省回落值班管理员
ACCOUNTS: dict[str, Account] = {
    "admin": Account("admin", "值班管理员", "admin"),
    "station-1": Account("station-1", "WEAT-0001 站点账号", "station", station="WEAT-0001"),
    "station-2": Account("station-2", "WEAT-0002 站点账号", "station", station="WEAT-0002"),
    "vendor": Account("vendor", "外协账号", "vendor"),
}
DEFAULT_ACCOUNT = ACCOUNTS["admin"]

# 目标范围标识：站点共享用站点编号，外协统一收敛到 "vendor"
VENDOR_SCOPE = "vendor"


@dataclass
class ShareGrant:
    """一条共享授权：把 entry_id 的记录共享给 scope（站点编号或 vendor）。"""

    entry_id: int
    scopes: list[str] = field(default_factory=list)
    source: str = ""  # 共享来源：发起共享的站点


class ShareCatalog:
    """共享目录：可见性判定、字段脱敏、共享授权的唯一来源。"""

    def __init__(self) -> None:
        # entry_id -> ShareGrant，集中保存，避免在业务记录里散落授权状态
        self._grants: dict[int, ShareGrant] = {}

    def account(self, key: str | None) -> Account:
        if key and key in ACCOUNTS:
            return ACCOUNTS[key]
        return DEFAULT_ACCOUNT

    def grant(self, entry_id: int, scopes: list[str], source: str) -> ShareGrant:
        scopes = [scope for scope in dict.fromkeys(scopes) if scope]
        record = self._grants.get(entry_id)
        if record is None:
            record = ShareGrant(entry_id=entry_id, scopes=scopes, source=source)
            self._grants[entry_id] = record
        else:
            record.scopes = scopes
            # 共享来源只在首次登记时落定，后续动作不覆盖
            record.source = record.source or source
        return record

    # ---- 可见性：三个入口共用的唯一判定 ----
    def can_view(self, account: Account, entry: dict[str, Any]) -> bool:
        owner = str(entry.get(OWNER_FIELD, ""))
        grant = self._grants.get(int(entry.get("id", 0)))
        scopes = grant.scopes if grant else []

        if account.is_admin:
            return True
        if account.kind == "station":
            # 本站点记录，或明确共享给本站点的记录
            return owner == account.station or account.station in scopes
        if account.is_vendor:
            return VENDOR_SCOPE in scopes
        return False

    def is_owner(self, account: Account, entry: dict[str, Any]) -> bool:
        return account.is_admin or str(entry.get(OWNER_FIELD, "")) == account.station

    def can_write(self, account: Account, entry: dict[str, Any]) -> bool:
        """外协只读：只有归属方（含管理员）能执行写动作。

        共享目录给的是“可见”，不等于“可写”，外协对共享记录的越权提交在此拦截。
        """
        return self.is_owner(account, entry)

    def visible_rows(self, account: Account, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if self.can_view(account, row)]

    def project(self, account: Account, entry: dict[str, Any]) -> dict[str, Any]:
        """按账号对单条记录做字段投影：跨站共享时脱敏敏感字段。

        列表和详情必须走同一投影，保证两个入口看到的字段一致。
        owner 一并返回，供前端按钮显隐与后端写校验保持同一判定。
        """
        view = dict(entry)
        if not self.is_owner(account, entry):
            for name in SENSITIVE_FIELDS:
                if name in view:
                    view[name] = MASK
        grant = self._grants.get(int(entry.get("id", 0)))
        if grant:
            view[SOURCE_FIELD] = grant.source
            view[ORIGIN_FIELD] = int(entry.get("id", 0))
            view[SHARED_WITH_FIELD] = list(grant.scopes)
        return view


# 进程内唯一共享目录实例：所有入口共享同一份授权与口径
share_catalog = ShareCatalog()


def seed_weather_shares() -> None:
    """登记演示共享关系：与 seed.py 的气象记录保持一致。

    - 记录 2（WEAT-0002）共享给 WEAT-0001：站点账号1能看到这条跨站记录，
      但风速等敏感字段按共享目录口径屏蔽。
    - 记录 3（WEAT-0003）共享给外协：外协可见但只读，越权写会被拒。
    """
    share_catalog.grant(2, ["WEAT-0001"], source="WEAT-0002")
    share_catalog.grant(3, [VENDOR_SCOPE], source="WEAT-0003")
