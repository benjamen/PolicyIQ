"""Filesystem-backed StorageAdapter. Root path from DOCUMENT_STORAGE_ROOT
(see .env.example) - local dev/first-deploy default, R2 implementation
comes later behind the same Protocol (app/storage/base.py)."""

from __future__ import annotations

import os
from pathlib import Path


class LocalDiskStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, data: bytes) -> str:
        path = self._path_for(key)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()


def storage_from_env() -> LocalDiskStorage:
    root = os.environ.get("DOCUMENT_STORAGE_ROOT", "./document_storage")
    return LocalDiskStorage(root)
