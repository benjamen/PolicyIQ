"""Storage adapter interface. `local_disk.py` is the only implementation
today (see docs/06-DEPLOYMENT-PLAN.md's "Live environments" - Cloudflare R2
was deliberately deferred to avoid a second new external account alongside
the VPS/domain work already done this project). An R2 implementation
conforming to this same Protocol is a swap-in later, not a rewrite."""

from __future__ import annotations

from typing import Protocol


class StorageAdapter(Protocol):
    def put(self, key: str, data: bytes) -> str:
        """Store `data` under `key`. Idempotent: re-putting identical bytes
        under a key that already exists is a no-op. Returns the key."""
        ...

    def get(self, key: str) -> bytes:
        ...

    def exists(self, key: str) -> bool:
        ...
