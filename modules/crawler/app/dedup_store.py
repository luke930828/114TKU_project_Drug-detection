"""URL / 圖片 hash 去重：改用 queue.db SQLite，啟動時從舊 JSON 匯入。"""
import json
import logging
import os
import sqlite3
from typing import Optional


class DedupStore:
    def __init__(
        self,
        db_path: str,
        url_json_path: Optional[str] = None,
        hash_json_path: Optional[str] = None,
    ):
        self.db_path = db_path
        self.url_json_path = url_json_path
        self.hash_json_path = hash_json_path
        self._ensure_schema()
        self._migrate_from_json()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS dedup_urls (url TEXT PRIMARY KEY, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS dedup_images (hash TEXT PRIMARY KEY, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()

    def _migrate_from_json(self) -> None:
        migrated_urls = 0
        migrated_hashes = 0
        with self._connect() as conn:
            if self.url_json_path and os.path.isfile(self.url_json_path):
                try:
                    with open(self.url_json_path, encoding="utf-8") as f:
                        urls = json.load(f)
                    for url in urls:
                        if url:
                            cur = conn.execute(
                                "INSERT OR IGNORE INTO dedup_urls (url) VALUES (?)", (url,)
                            )
                            migrated_urls += cur.rowcount
                except Exception as e:
                    logging.warning(f"[DedupStore] URL JSON 匯入失敗: {e}")

            if self.hash_json_path and os.path.isfile(self.hash_json_path):
                try:
                    with open(self.hash_json_path, encoding="utf-8") as f:
                        hashes = json.load(f)
                    for h in hashes:
                        if h:
                            cur = conn.execute(
                                "INSERT OR IGNORE INTO dedup_images (hash) VALUES (?)", (h,)
                            )
                            migrated_hashes += cur.rowcount
                except Exception as e:
                    logging.warning(f"[DedupStore] Image JSON 匯入失敗: {e}")
            conn.commit()

        if migrated_urls or migrated_hashes:
            logging.info(
                f"[DedupStore] 已從 JSON 匯入 dedup_urls={migrated_urls}, dedup_images={migrated_hashes}"
            )

    def has_url(self, url: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM dedup_urls WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
            return row is not None

    def add_url(self, url: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO dedup_urls (url) VALUES (?)", (url,))
            conn.commit()

    def has_image_hash(self, img_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM dedup_images WHERE hash = ? LIMIT 1", (img_hash,)
            ).fetchone()
            return row is not None

    def add_image_hash(self, img_hash: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO dedup_images (hash) VALUES (?)", (img_hash,))
            conn.commit()

    def url_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM dedup_urls").fetchone()
            return row[0] if row else 0

    def image_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM dedup_images").fetchone()
            return row[0] if row else 0
