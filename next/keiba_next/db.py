"""JRA公式 DB（jv_data.db 等）への読み取り専用アクセス。

現行システムの接続コードは流用・改変しない。ここは新系統専用。
"""

from __future__ import annotations

from pathlib import Path


def resolve_db_path(db: str | Path) -> Path:
    path = Path(db).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"JRA DB not found: {path}. Pass --db /path/to/jv_data.db"
        )
    return path


def ping(db: str | Path) -> dict:
    """DBファイルの存在確認のみ（スキーマ接続は M1 で拡張）。"""
    path = resolve_db_path(db)
    return {"ok": True, "db": str(path), "size_bytes": path.stat().st_size}
