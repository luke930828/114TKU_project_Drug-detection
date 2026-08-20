"""
把舊 Record 紀錄遷移到精簡檔（不覆蓋、追加；先遷移再允許清理）。
可獨立執行：python migrate_record_legacy.py
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any

from record_paths import (
    append_text_line,
    append_visited,
    append_nlp_record,
    get_record_paths,
    _load_json_list,
    _save_json_list,
)


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
SCORE_RE = re.compile(
    r"\[SCORE\]\s+(\w+)\s+score=([-\d.]+)\s+\|\s+(\S+)"
)
SAVE_RE = re.compile(
    r"\[TRACK B\]\s+入庫\+送封包\s+(\w+)\s+score=([-\d.]+)\s+\|\s+(\S+)"
)
INV_RE = re.compile(r"Investigating \(Full\) \[Attempt \d+\]:\s+(\S+)")
SHOP_RE = re.compile(r"^\[(\w+)\]\s+score=([-\d.]+)\s+\|\s+(\S+)")
URLS_TXT_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+Score:\s*([-\d.]+)\s+\|\s+(\S+)"
)


def _ts_from_line(line: str) -> str:
    m = TS_RE.match(line)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrate_operation_log(paths: Dict) -> Tuple[int, int]:
    """operation_v2.log / log_engine.log → log_24h.txt；並抽出造訪／入庫摘要。"""
    src_candidates = [
        "Record/operation_v2.log",
        "Record/log_engine.log",
        "Record/log_all.log",
    ]
    dest = paths["log_24h"]
    existing = ""
    if os.path.isfile(dest):
        with open(dest, encoding="utf-8", errors="replace") as f:
            existing = f.read()

    merged_lines = 0
    visits = 0
    nlp_added = 0
    seen_nlp: Set[str] = set()

    # 已有 nlp 的 url 避免重複灌
    for item in _load_json_list(paths["json_nlp_text"]):
        if isinstance(item, dict) and item.get("url"):
            seen_nlp.add(str(item["url"]))

    for src in src_candidates:
        if not os.path.isfile(src):
            continue
        marker = f"# ===== 遷移自 {os.path.basename(src)} ====="
        if marker in existing:
            print(f"skip already migrated: {src}")
            continue
        with open(src, encoding="utf-8", errors="replace") as f:
            body = f.read()
        if not body.strip():
            continue
        append_text_line(dest, f"\n{marker}\n")
        append_text_line(dest, body if body.endswith("\n") else body + "\n")
        merged_lines += body.count("\n") + 1

        for line in body.splitlines():
            ts = _ts_from_line(line)
            m = SAVE_RE.search(line) or SCORE_RE.search(line)
            if m:
                tier, score, url = m.group(1), m.group(2), m.group(3)
                append_visited(
                    paths, url, source="24H", tier=tier, score=score, status="migrated"
                )
                visits += 1
                if url not in seen_nlp and "入庫" in line:
                    try:
                        score_v: Any = float(score)
                    except ValueError:
                        score_v = score
                    append_nlp_record(
                        paths,
                        {
                            "timestamp": ts,
                            "url": url,
                            "tier": tier,
                            "score": score_v,
                            "matched": [],
                            "fingerprints": [],
                            "entities": {},
                            "text_content": "",
                            "source": "24H-migrated",
                            "note": "從舊 log 還原（無原文，僅評分摘要）",
                        },
                    )
                    seen_nlp.add(url)
                    nlp_added += 1
                continue
            m2 = INV_RE.search(line)
            if m2:
                append_visited(
                    paths, m2.group(1), source="24H", status="investigated-migrated"
                )
                visits += 1

    return merged_lines, visits + nlp_added


def migrate_potential_shops(paths: Dict) -> int:
    src = "Record/Potential_Shops.txt"
    if not os.path.isfile(src):
        return 0
    n = 0
    seen = {str(i.get("url")) for i in _load_json_list(paths["json_nlp_text"]) if isinstance(i, dict)}
    with open(src, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = SHOP_RE.search(line.strip())
            if not m:
                continue
            tier, score, url = m.group(1), m.group(2), m.group(3)
            append_visited(paths, url, source="24H", tier=tier, score=score, status="shop-list")
            if url not in seen:
                append_nlp_record(
                    paths,
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "url": url,
                        "tier": tier,
                        "score": score,
                        "matched": [],
                        "text_content": "",
                        "source": "Potential_Shops-migrated",
                    },
                )
                seen.add(url)
                n += 1
    # 全文也併入 log_24h
    with open(src, encoding="utf-8", errors="replace") as f:
        body = f.read()
    marker = "# ===== 遷移自 Potential_Shops.txt ====="
    with open(paths["log_24h"], encoding="utf-8", errors="replace") as f:
        cur = f.read()
    if marker not in cur and body.strip():
        append_text_line(paths["log_24h"], f"\n{marker}\n{body}\n")
    return n


def migrate_visited_all(paths: Dict) -> int:
    n = 0
    for src in ("Record/visited_all.txt", "Record/visited_urls.txt"):
        if not os.path.isfile(src):
            continue
        marker = f"# ===== 遷移自 {os.path.basename(src)} ====="
        with open(paths["log_visited"], encoding="utf-8", errors="replace") as f:
            cur = f.read()
        if marker in cur:
            continue
        with open(src, encoding="utf-8", errors="replace") as f:
            body = f.read()
        append_text_line(paths["log_visited"], f"\n{marker}\n{body}\n")
        n += body.count("\n")
    return n


def migrate_urls_txt(paths: Dict) -> int:
    src = "testHTML/urls.txt"
    if not os.path.isfile(src):
        return 0
    n = 0
    with open(src, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = URLS_TXT_RE.search(line)
            if not m:
                continue
            ts, score, url = m.group(1), m.group(2), m.group(3)
            append_text_line(
                paths["log_visited"],
                f"[{ts}] source=24H score={score} status=urls.txt | {url}",
            )
            n += 1
    return n


def migrate_db_urls(paths: Dict) -> int:
    n = 0
    for db in (paths.get("db_monitor"), paths.get("db_queue"), "Record/monitor_state.db", "Record/queue.db"):
        if not db or not os.path.isfile(db):
            continue
        try:
            conn = sqlite3.connect(db)
            rows = conn.execute(
                "SELECT url, status, added_at FROM url_state ORDER BY added_at"
            ).fetchall()
            conn.close()
        except Exception as e:
            print(f"db skip {db}: {e}")
            continue
        status_map = {0: "queued", 1: "in_progress", 2: "done"}
        for url, status, added_at in rows:
            append_text_line(
                paths["log_visited"],
                f"[{added_at or ''}] source=DB status={status_map.get(status, status)} | {url}",
            )
            n += 1
    return n


def migrate_intel_report(paths: Dict) -> Tuple[int, int]:
    """若 intel_report / reports 還在，拆進 nlp_text.json + images.json。"""
    n_nlp = n_img = 0
    for src in ("Record/intel_report.json", "Record/reports.json"):
        if not os.path.isfile(src):
            continue
        try:
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"intel load fail {src}: {e}")
            continue
        if not isinstance(data, list):
            continue
        existing_nlp = {
            f"{i.get('url')}|{i.get('timestamp')}"
            for i in _load_json_list(paths["json_nlp_text"])
            if isinstance(i, dict)
        }
        existing_img = {
            f"{i.get('url')}|{i.get('timestamp')}"
            for i in _load_json_list(paths["json_images"])
            if isinstance(i, dict)
        }
        nlp_items = _load_json_list(paths["json_nlp_text"])
        img_items = _load_json_list(paths["json_images"])
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            ts = item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            key = f"{url}|{ts}"
            if key not in existing_nlp:
                nlp_items.append(
                    {
                        "timestamp": ts,
                        "url": url,
                        "tier": item.get("tier"),
                        "score": item.get("score"),
                        "matched": item.get("matched") or [],
                        "fingerprints": item.get("fingerprints") or [],
                        "entities": item.get("entities") or {},
                        "text_content": item.get("text_content") or "",
                        "source": "intel_report-migrated",
                    }
                )
                existing_nlp.add(key)
                n_nlp += 1
            if key not in existing_img:
                img_items.append(
                    {
                        "timestamp": ts,
                        "url": url,
                        "tier": item.get("tier"),
                        "score": item.get("score"),
                        "screenshot_b64": item.get("screenshot_b64") or "",
                        "full_screenshot_base64": item.get("full_screenshot_base64") or "",
                        "product_images": item.get("product_images") or [],
                        "source": "intel_report-migrated",
                    }
                )
                existing_img.add(key)
                n_img += 1
            append_visited(
                paths,
                url,
                source="24H",
                tier=str(item.get("tier") or ""),
                score=item.get("score", ""),
                status="intel-migrated",
            )
        _save_json_list(paths["json_nlp_text"], nlp_items)
        _save_json_list(paths["json_images"], img_items)
        print(f"migrated intel from {src}: nlp+={n_nlp} images+={n_img}")
    return n_nlp, n_img


def migrate_log_all_to_manual(paths: Dict) -> int:
    src = "Record/log_all.log"
    if not os.path.isfile(src):
        return 0
    dest = paths["log_manual"]
    marker = "# ===== 遷移自 log_all.log（含手動段落）====="
    with open(dest, encoding="utf-8", errors="replace") as f:
        cur = f.read()
    if marker in cur:
        return 0
    with open(src, encoding="utf-8", errors="replace") as f:
        body = f.read()
    # 手動相關行優先寫入手動 log；全文也備份進 log_24h 以免遺失
    manual_lines = [
        ln for ln in body.splitlines() if "MANUAL" in ln or "| MANUAL" in ln
    ]
    append_text_line(dest, f"\n{marker}\n")
    if manual_lines:
        append_text_line(dest, "\n".join(manual_lines) + "\n")
    else:
        append_text_line(dest, body if body.endswith("\n") else body + "\n")
    append_text_line(paths["log_24h"], f"\n{marker}\n")
    append_text_line(paths["log_24h"], body if body.endswith("\n") else body + "\n")
    return len(manual_lines) or body.count("\n")


def main() -> None:
    paths = get_record_paths()
    os.makedirs(paths["dir"], exist_ok=True)
    for key in ("log_24h", "log_manual", "log_visited"):
        if not os.path.isfile(paths[key]):
            append_text_line(paths[key], f"# created {_ts_from_line('')}\n")
    for key in ("json_images", "json_nlp_text"):
        if not os.path.isfile(paths[key]):
            _save_json_list(paths[key], [])

    print("migrate intel...", migrate_intel_report(paths))
    print("migrate Potential_Shops...", migrate_potential_shops(paths))
    print("migrate visited_all...", migrate_visited_all(paths))
    print("migrate operation log...", migrate_operation_log(paths))
    print("migrate log_all...", migrate_log_all_to_manual(paths))
    print("migrate urls.txt...", migrate_urls_txt(paths))
    print("migrate db urls...", migrate_db_urls(paths))
    print("done.")
    print("sizes:", {k: os.path.getsize(paths[k]) for k in (
        "log_24h", "log_manual", "log_visited", "json_nlp_text", "json_images"
    ) if os.path.isfile(paths[k])})


if __name__ == "__main__":
    main()
