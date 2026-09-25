"""监测报警业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "alarm"
REQUIRED_FIELDS = ["报警编号", "报警类型", "报警等级"]
STATUS_ORDER = ["待确认", "已确认", "已处置", "已忽略"]
ACTION_RULES = {"确认报警": "已确认", "处置报警": "已处置", "忽略报警": "已忽略"}
NEGATIVE_ACTIONS = ["忽略报警"]

PENDING_STATUS = STATUS_ORDER[0]
HIGH_LEVELS = {"高", "一级", "1级", "I级", "Ⅰ级", "紧急"}


def _has_confirmer(row: dict[str, Any]) -> bool:
    return bool(str(row.get("确认人员") or "").strip())


def _is_pending_confirm(row: dict[str, Any]) -> bool:
    """待确认口径：状态仍是待确认，且已指派确认人员；已确认、已处置、已忽略都不算。"""
    return row.get("status") == PENDING_STATUS and _has_confirmer(row)


def _needs_confirmer(row: dict[str, Any]) -> bool:
    """确认人员为空的待确认报警：单独标出，不计入待确认数量。"""
    return row.get("status") == PENDING_STATUS and not _has_confirmer(row)


def _is_high_level(row: dict[str, Any]) -> bool:
    return str(row.get("报警等级") or "").strip() in HIGH_LEVELS


class AlarmService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("报警编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        summary = self.summarize(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total, summary

    def summarize(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        """概览卡片口径：在过滤后的当前列表上实时重算，和列表、详情保持同一份数据。"""
        today = date.today().isoformat()
        return {
            "today": sum(1 for row in rows if str(row.get("触发时间") or "").startswith(today)),
            "pending_confirm": sum(1 for row in rows if _is_pending_confirm(row)),
            "missing_confirmer": sum(1 for row in rows if _needs_confirmer(row)),
            "high_level": sum(1 for row in rows if _is_high_level(row)),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["报警状态"] = STATUS_ORDER[0]
        entry["pending"] = _is_pending_confirm(entry)
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"报警事件 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于监测报警可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["报警状态"] = target
        entry["pending"] = _is_pending_confirm(entry)
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"报警事件已{action}"
