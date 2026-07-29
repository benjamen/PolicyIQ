from app.storage.keys import build_storage_key, slugify
from app.storage.local_disk import LocalDiskStorage


def test_put_get_roundtrip(tmp_path):
    storage = LocalDiskStorage(tmp_path)
    key = "aia/life_cover/pds/abc123def456-wording.pdf"
    storage.put(key, b"hello world")

    assert storage.exists(key)
    assert storage.get(key) == b"hello world"


def test_reput_identical_bytes_is_noop(tmp_path):
    storage = LocalDiskStorage(tmp_path)
    key = "aia/life_cover/pds/abc123def456-wording.pdf"
    storage.put(key, b"hello world")
    path = storage._path_for(key)
    first_mtime = path.stat().st_mtime_ns

    storage.put(key, b"hello world")
    assert path.stat().st_mtime_ns == first_mtime


def test_not_exists_for_missing_key(tmp_path):
    storage = LocalDiskStorage(tmp_path)
    assert not storage.exists("nope/nope/nope/000000000000-x.pdf")


def test_build_storage_key_format():
    key = build_storage_key(
        insurer="AIA New Zealand",
        product_type="life_cover",
        doc_type="pds",
        sha256_hex="abcdef0123456789",
        filename="Life Policy Wording.pdf",
    )
    assert key == "aia-new-zealand/life-cover/pds/abcdef012345-life-policy-wording.pdf"


def test_slugify_strips_disallowed_chars():
    assert slugify("AIA New Zealand!!") == "aia-new-zealand"
    assert slugify("") == "unknown"
