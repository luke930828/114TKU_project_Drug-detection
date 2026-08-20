import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from record_paths import get_record_paths


# 標準 phase 命名（手動 / 24H 頁面爬取共用）
CRAWL_PHASES = (
    "START",
    "BROWSER",
    "ROUTE",
    "NAV",
    "POPUP",
    "AUTH",
    "SCROLL",
    "SCORE",
    "SCREENSHOT",
    "IMAGES",
    "SAVE",
    "WEBHOOK",
    "DB",
    "RESULT",
    "ERROR",
    "DONE",
)

# 24H 引擎層級 phase
ENGINE_PHASES = (
    "ENGINE_START",
    "ENGINE_STOP",
    "TRACK_A",
    "TRACK_B",
    "HARVEST",
    "QUEUE",
    "WORKER",
    "WEBHOOK",
    "ERROR",
)


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _truncate_url(url: str, max_len: int = 90) -> str:
    if len(url) <= max_len:
        return url
    return url[: max_len - 3] + "..."


class RecordLogWriter:
    """將日誌寫入 Record/log_all.log 與 log_all.jsonl（統一彙總）。"""

    CATEGORY_TO_KEY = {
        "manual": "manual",
        "automated_24h": "page_24h",
        "visits": "visit",
        "engine": "engine_24h",
    }

    CATEGORY_LABELS = {
        "manual": "MANUAL",
        "automated_24h": "24H-PAGE",
        "visits": "VISIT",
        "engine": "24H-ENGINE",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, category: str = "manual"):
        self.config = config or {}
        log_cfg = self.config.get("crawl_logging") or {}
        rp = get_record_paths(self.config)
        # 精簡：手動 → log_manual.txt；24H／engine → log_24h.txt；不再寫 jsonl
        if category == "manual":
            self.unified_text = rp.get("log_manual", "Record/log_manual.txt")
        else:
            self.unified_text = rp.get("log_24h", "Record/log_24h.txt")
        self.visited_path = rp.get("log_visited", "Record/visited.txt")
        self.write_text = bool(log_cfg.get("write_text_log", True))
        self.write_jsonl = bool(log_cfg.get("write_jsonl", False))
        self.category = category if category in self.CATEGORY_TO_KEY else "manual"
        self._label = self.CATEGORY_LABELS[self.category]

    def _paths_for_today(self) -> Dict[str, str]:
        os.makedirs(os.path.dirname(self.unified_text) or "Record", exist_ok=True)
        return {"text": self.unified_text, "jsonl": self.unified_text}

    def _rotate_if_needed(self, path: str, max_bytes: int = 10 * 1024 * 1024) -> None:
        try:
            if os.path.isfile(path) and os.path.getsize(path) > max_bytes:
                rotated = path + ".1"
                if os.path.isfile(rotated):
                    os.remove(rotated)
                os.replace(path, rotated)
        except Exception:
            pass

    @staticmethod
    def _format_extra(extra: Dict[str, Any]) -> str:
        if not extra:
            return ""
        parts = [f"{k}={v}" for k, v in extra.items() if v is not None]
        return " | " + " | ".join(parts) if parts else ""

    def _append_text_header_if_new(self, path: str) -> None:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return
        header = (
            "# 爬蟲 log（手動 → log_manual.txt；24H → log_24h.txt）\n"
            "# 造訪總表另見 visited.txt\n"
        )
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception:
            pass

    def write_step(
        self,
        phase: str,
        message: str,
        url: str = "",
        elapsed_ms: Optional[int] = None,
        level: str = "info",
        **extra: Any,
    ) -> Dict[str, Any]:
        ts = _now_str()
        event: Dict[str, Any] = {
            "ts": ts,
            "category": self._label,
            "phase": phase.upper(),
            "level": level,
            "url": url,
            "message": message,
        }
        if elapsed_ms is not None:
            event["elapsed_ms"] = elapsed_ms
        event.update(extra)

        paths = self._paths_for_today()

        elapsed_part = f"+{elapsed_ms:6}ms" if elapsed_ms is not None else "       -"
        url_part = _truncate_url(url) if url else "-"
        line = (
            f"{ts} | {self._label:10} | {phase.upper():10} | {elapsed_part} "
            f"| {url_part:90} | {message}{self._format_extra(extra)}\n"
        )

        if self.write_text:
            try:
                self._append_text_header_if_new(paths["text"])
                with open(paths["text"], "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as exc:
                logging.debug(f"[RecordLog] text write failed: {exc}")

        if self.write_jsonl:
            try:
                with open(paths["jsonl"], "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
                self._rotate_if_needed(paths["jsonl"])
            except Exception as exc:
                logging.debug(f"[RecordLog] jsonl write failed: {exc}")

        return event

    def write_visit(
        self,
        url: str,
        task_type: str,
        status: str,
        total_ms: int,
        **extra: Any,
    ) -> None:
        """純網頁造訪紀錄（每 URL 一筆摘要）。"""
        from record_paths import append_visited

        label = "MANUAL" if task_type == "manual" else "24H"
        rp = get_record_paths(self.config)
        append_visited(
            rp,
            url,
            source=label,
            status=status,
            tier=str(extra.get("tier") or ""),
            score=extra.get("score", ""),
        )
        # 同步一行到對應 log
        ts = _now_str()
        target = (
            rp.get("log_manual", "Record/log_manual.txt")
            if task_type == "manual"
            else rp.get("log_24h", "Record/log_24h.txt")
        )
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(
                    f"{ts} | VISIT | {label} | {status} | {total_ms}ms | {url}\n"
                )
        except Exception as exc:
            logging.debug(f"[RecordLog] visit log write failed: {exc}")


class CrawlLogger:
    """單一 URL 爬取過程的分步日誌（manual / automated_24h）。"""

    def __init__(
        self,
        url: str,
        task_type: str = "manual",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.url = url
        self.task_type = task_type
        self.config = config or {}
        self._start = time.monotonic()
        self._events: List[Dict[str, Any]] = []

        category = "manual" if task_type == "manual" else "automated_24h"
        self._writer = RecordLogWriter(self.config, category=category)
        self._visit_writer = RecordLogWriter(self.config, category="visits")

        log_cfg = self.config.get("crawl_logging") or {}
        self._terminal_enabled = bool(log_cfg.get("log_to_terminal", True))
        self._terminal_level = (log_cfg.get("terminal_level") or "info").lower()

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)

    def _should_log_terminal(self, level: str) -> bool:
        if not self._terminal_enabled:
            return False
        order = {"debug": 10, "info": 20, "warning": 30, "error": 40}
        return order.get(level, 20) >= order.get(self._terminal_level, 20)

    def _emit(self, level: str, phase: str, message: str, **extra: Any) -> None:
        elapsed_ms = self._elapsed_ms()
        event = self._writer.write_step(
            phase=phase,
            message=message,
            url=self.url,
            elapsed_ms=elapsed_ms,
            level=level,
            task_type=self.task_type,
            **extra,
        )
        self._events.append(event)

        if self._should_log_terminal(level):
            label = "MANUAL" if self.task_type == "manual" else "24H"
            detail = self._writer._format_extra(extra)
            line = (
                f"[{label}][{phase.upper()}] +{elapsed_ms}ms | {self.url} | {message}{detail}"
            )
            getattr(logging, level, logging.info)(line)

    def start(self, **extra: Any) -> None:
        self._emit("info", "START", "開始爬取", **extra)

    def phase(self, phase: str, message: str, level: str = "info", **extra: Any) -> None:
        self._emit(level, phase.upper(), message, **extra)

    def done(self, status: str, **extra: Any) -> None:
        total_ms = self._elapsed_ms()
        self._emit("info", "DONE", "爬取結束", status=status, total_ms=total_ms, **extra)
        self._visit_writer.write_visit(
            url=self.url,
            task_type=self.task_type,
            status=status,
            total_ms=total_ms,
            **{k: v for k, v in extra.items() if k not in ("status", "total_ms")},
        )

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)


class EngineLogger:
    """24H 雙軌引擎（Track A / Track B）運行日誌。"""

    _instance: Optional["EngineLogger"] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._writer = RecordLogWriter(self.config, category="engine")
        log_cfg = self.config.get("crawl_logging") or {}
        self._terminal_enabled = bool(log_cfg.get("log_to_terminal", True))

    @classmethod
    def get(cls, config: Optional[Dict[str, Any]] = None) -> "EngineLogger":
        if cls._instance is None:
            cls._instance = EngineLogger(config)
        elif config and cls._instance.config != config:
            cls._instance = EngineLogger(config)
        return cls._instance

    def phase(self, phase: str, message: str, level: str = "info", **extra: Any) -> None:
        url = extra.get("url", "")
        self._writer.write_step(
            phase=phase.upper(),
            message=message,
            url=url,
            level=level,
            **extra,
        )
        if self._terminal_enabled:
            detail = self._writer._format_extra(extra)
            getattr(logging, level, logging.info)(
                f"[24H-ENGINE][{phase.upper()}] {message}{detail}"
            )

    def engine_start(self, **extra: Any) -> None:
        self.phase("ENGINE_START", "24H 雙軌引擎啟動", **extra)

    def engine_stop(self, **extra: Any) -> None:
        self.phase("ENGINE_STOP", "24H 雙軌引擎停止", **extra)


def get_engine_logger(config: Optional[Dict[str, Any]] = None) -> EngineLogger:
    return EngineLogger.get(config)
