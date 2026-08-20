"""
Record 目錄約定（精簡版）：

  log_24h.txt      24H 雙軌運行紀錄
  log_manual.txt   手動爬紀錄
  visited.txt      所有探訪過的網址 + 時間
  images.json      截圖／商品圖 base64
  nlp_text.json    NLP／頁面文字與評分摘要
  queue.db / monitor_state.db  佇列（SQLite，非 JSON）
"""
import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional


DEFAULT_RECORD_PATHS: Dict[str, Any] = {
    "dir": "Record",
    "db_queue": "Record/queue.db",
    "db_monitor": "Record/monitor_state.db",
    "log_24h": "Record/log_24h.txt",
    "log_manual": "Record/log_manual.txt",
    "log_visited": "Record/visited.txt",
    "json_images": "Record/images.json",
    "json_nlp_text": "Record/nlp_text.json",
    # 相容舊鍵（導向新檔，避免舊程式炸）
    "json_reports": "Record/nlp_text.json",
    "json_reports_jsonl": "Record/nlp_text.json",
    "json_dedup_urls": "Record/dedup_urls.json",
    "json_dedup_images": "Record/dedup_images.json",
    "json_webhook_failed": "Record/log_24h.txt",
    "log_engine": "Record/log_24h.txt",
    "log_unified_text": "Record/log_24h.txt",
    "log_unified_jsonl": "Record/log_24h.txt",
    "log_archive_dir": "Record/_archive",
    "log_dirs": {},
}

# 啟動時可刪／歸檔的雜訊檔
OBSOLETE_NAMES = (
    "operation_v2.log",
    "operation_v2.log.1",
    "log_engine.log",
    "log_engine.log.1",
    "log_all.log",
    "log_all.log.1",
    "log_all.jsonl",
    "log_all.jsonl.1",
    "Potential_Shops.txt",
    "intel_report.json",
    "reports.json",
    "reports.jsonl",
    "search_health.json",
    "webhook_failed.jsonl",
    "dedup_urls.json",
    "dedup_images.json",
    "seen_urls.json",
    "seen_images.json",
    "visited_all.txt",
    "README.txt",
)

OBSOLETE_DIRS = (
    "log_manual",
    "log_visit",
    "log_24h_page",
    "log_24h_engine",
    "_logs_old",
    "_archive",
)


def get_record_paths(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = config or {}
    merged = {**DEFAULT_RECORD_PATHS, **(cfg.get("record_paths") or {})}
    return merged


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_text_line(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line if line.endswith("\n") else line + "\n")


def append_visited(
    paths: Dict[str, Any],
    url: str,
    *,
    source: str = "24H",
    tier: str = "",
    score: Any = "",
    status: str = "",
) -> None:
    path = paths.get("log_visited", "Record/visited.txt")
    parts = [f"[{_now()}]", f"source={source}"]
    if tier:
        parts.append(f"tier={tier}")
    if score != "" and score is not None:
        parts.append(f"score={score}")
    if status:
        parts.append(f"status={status}")
    parts.append(f"| {url}")
    append_text_line(path, " ".join(parts))


def _load_json_list(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json_list(path: str, items: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def append_images_record(paths: Dict[str, Any], record: Dict[str, Any]) -> None:
    path = paths.get("json_images", "Record/images.json")
    items = _load_json_list(path)
    items.append(record)
    _save_json_list(path, items)


def append_nlp_record(paths: Dict[str, Any], record: Dict[str, Any]) -> None:
    path = paths.get("json_nlp_text", "Record/nlp_text.json")
    items = _load_json_list(path)
    items.append(record)
    _save_json_list(path, items)


def cleanup_obsolete_record_files(paths: Dict[str, Any], *, force: bool = False) -> List[str]:
    """靜默清掉明顯多餘的舊檔；不做 migrate（遷移請手動跑 migrate_record_legacy.py）。"""
    record_dir = paths.get("dir", "Record")
    keep = {
        os.path.normpath(paths.get("log_24h", "")),
        os.path.normpath(paths.get("log_manual", "")),
        os.path.normpath(paths.get("log_visited", "")),
        os.path.normpath(paths.get("json_images", "")),
        os.path.normpath(paths.get("json_nlp_text", "")),
        os.path.normpath(paths.get("db_queue", "")),
        os.path.normpath(paths.get("db_monitor", "")),
        os.path.normpath(os.path.join(record_dir, "monitor_state.db")),
        os.path.normpath(os.path.join(record_dir, "queue.db")),
        os.path.normpath(os.path.join(record_dir, "README.txt")),
        os.path.normpath(os.path.join(record_dir, "operation_v2.log.bak")),
    }
    removed: List[str] = []

    for name in OBSOLETE_NAMES:
        if name == "operation_v2.log" and not force:
            continue
        p = os.path.join(record_dir, name)
        if os.path.normpath(p) in keep:
            continue
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed.append(name)
            except OSError:
                pass

    for name in OBSOLETE_DIRS:
        p = os.path.join(record_dir, name)
        if os.path.isdir(p):
            try:
                shutil.rmtree(p)
                removed.append(name + "/")
            except OSError:
                pass

    return removed


def _write_readme(paths: Dict[str, Any]) -> None:
    readme = os.path.join(paths["dir"], "README.txt")
    with open(readme, "w", encoding="utf-8") as f:
        f.write(
            "Record 資料夾（精簡）\n"
            "==================\n"
            "\n"
            "  log_24h.txt       24H 雙軌運行紀錄\n"
            "  log_manual.txt    手動爬紀錄\n"
            "  visited.txt       所有探訪網址 + 時間\n"
            "  images.json       截圖／商品圖 base64\n"
            "  nlp_text.json     頁面文字／評分（NLP 用）\n"
            "  monitor_state.db  24H 佇列（SQLite）\n"
            "  queue.db          手動／共用佇列（若有）\n"
            "\n"
            "舊資料遷移（僅手動）：python migrate_record_legacy.py\n"
        )


def ensure_record_layout(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """確保 Record 目錄與約定檔存在；啟動時安靜、不跑遷移、不刷 log。"""
    paths = get_record_paths(config)
    os.makedirs(paths["dir"], exist_ok=True)
    for key in ("log_24h", "log_manual", "log_visited"):
        p = paths[key]
        if not os.path.isfile(p):
            append_text_line(p, f"# {_now()} created\n")
    for key in ("json_images", "json_nlp_text"):
        p = paths[key]
        if not os.path.isfile(p):
            _save_json_list(p, [])
    # 不在啟動時 migrate；也不寫「已清理」到 log_24h
    cleanup_obsolete_record_files(paths)
    if not os.path.isfile(os.path.join(paths["dir"], "README.txt")):
        _write_readme(paths)
    return paths


def load_config_record_paths(config_path: str = "config.json") -> Dict[str, Any]:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return get_record_paths(json.load(f))
    except OSError:
        return get_record_paths()
