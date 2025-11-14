import hashlib
import secrets
import re
from typing import Optional


def gen_single_use_key() -> str:
    prefix = f"{secrets.randbelow(900000)+100000}"  # 6 dígitos
    variant = str(secrets.randbelow(3) + 1)  # 1..3
    suffix = secrets.token_hex(32)  # 64 hex
    return f"{prefix}-{variant}_{suffix}"


def key_to_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def normalize_key(text: str) -> Optional[str]:
    text = (text or "").replace("\n", " ").strip()
    m = re.search(r"(\d{6}-[0-9]+_[A-Za-z0-9]{20,})", text)
    if m:
        return m.group(1)
    m = re.search(r"([A-Za-z0-9_-]{20,})", text)
    return m.group(1) if m else None
