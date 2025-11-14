import os
import aiosqlite
import hashlib
from datetime import datetime, timezone
from typing import Optional, List
from config import DB_PATH, STORAGE_DIR

os.makedirs(STORAGE_DIR, exist_ok=True)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_for(filename: str) -> str:
    return os.path.join(STORAGE_DIR, filename)


CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files(
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  key_hash     TEXT UNIQUE,
  filename     TEXT,
  content      BLOB,
  uploader_id  INTEGER,
  used         INTEGER DEFAULT 0,
  created_at   TEXT,
  file_sha     TEXT,
  expires_at   TEXT,
  used_by      INTEGER,
  used_at      TEXT
)
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_FILES)
        await db.commit()


async def file_exists_by_hash(file_sha: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM files WHERE file_sha = ? LIMIT 1", (file_sha,)
        )
        return (await cur.fetchone()) is not None


async def insert_file(
    key_hash: str,
    stored_name: str,
    data: bytes,
    uploader_id: int,
    created_at_iso: str,
    file_sha: str,
    expires_at_iso: Optional[str],
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO files(key_hash, filename, content, uploader_id, used,
                              created_at, file_sha, expires_at)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                key_hash,
                stored_name,
                data,
                uploader_id,
                created_at_iso,
                file_sha,
                expires_at_iso,
            ),
        )
        await db.commit()


async def get_file_by_keyhash(key_hash: str) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, filename, content, used, expires_at, uploader_id FROM files WHERE key_hash = ?",
            (key_hash,),
        )
        return await cur.fetchone()


async def mark_used(fid: int, used_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE files SET used = 1, used_by = ?, used_at = ? WHERE id = ? AND used = 0",
            (used_by, datetime.now(timezone.utc).isoformat(), fid),
        )
        await db.commit()


async def purge_expired_and_used():
    now_iso = datetime.now(timezone.utc).isoformat()
    to_delete: List[int] = []
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id, filename FROM files
            WHERE used = 1 OR (expires_at IS NOT NULL AND expires_at < ?)
            """,
            (now_iso,),
        )
        rows = await cur.fetchall()
        for fid, fname in rows:
            try:
                fpath = path_for(os.path.basename(fname))
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                pass
            to_delete.append(fid)

        if to_delete:
            q = f"DELETE FROM files WHERE id IN ({','.join('?'*len(to_delete))})"
            await db.execute(q, to_delete)
            await db.commit()
