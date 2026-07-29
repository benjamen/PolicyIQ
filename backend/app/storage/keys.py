"""Content-addressed storage key scheme, per docs/04-CRAWLER-STRATEGY.md:
{insurer}/{product_type}/{doc_type}/{sha256[:12]}-{filename} - the hash
prefix is what makes "never overwrite" a structural property rather than a
runtime check (same bytes always land at the same key)."""

from __future__ import annotations

import re

_SLUG_DISALLOWED = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_DISALLOWED.sub("-", value.strip().lower()).strip("-")
    return slug or "unknown"


def build_storage_key(
    *, insurer: str, product_type: str, doc_type: str, sha256_hex: str, filename: str
) -> str:
    insurer_slug = slugify(insurer)
    product_slug = slugify(product_type)
    doc_type_slug = slugify(doc_type)
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + (
        f".{filename.rsplit('.', 1)[1].lower()}" if "." in filename else ""
    )
    return f"{insurer_slug}/{product_slug}/{doc_type_slug}/{sha256_hex[:12]}-{safe_filename}"
