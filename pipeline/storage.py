"""Copy pipeline artifacts to and from object storage (MinIO locally, Cloud Storage on the VM).

`EAE_STORAGE_URL` is `s3://bucket` (MinIO; endpoint in `EAE_S3_ENDPOINT`) or
`gs://bucket` (the VM's service account authenticates; no key file).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _fs(url: str) -> Any:
    import fsspec

    if url.startswith("s3://"):
        endpoint = os.environ.get("EAE_S3_ENDPOINT")
        return fsspec.filesystem("s3", client_kwargs={"endpoint_url": endpoint} if endpoint else {})
    if url.startswith("gs://"):
        return fsspec.filesystem("gcs")
    raise ValueError("EAE_STORAGE_URL must start with s3:// or gs://")


def push(local_processed: Path, url: str, prefix: str = "processed") -> int:
    fs = _fs(url)
    dest = f"{url.rstrip('/')}/{prefix}"
    files = [p for p in local_processed.rglob("*") if p.is_file() and not p.name.endswith(".tmp")]
    for p in files:
        fs.put_file(str(p), f"{dest}/{p.relative_to(local_processed).as_posix()}")
    return len(files)


def pull(url: str, local_processed: Path, prefix: str = "processed") -> int:
    fs = _fs(url)
    src = f"{url.rstrip('/')}/{prefix}"
    n = 0
    for remote in fs.find(src):
        rel = remote.split(f"/{prefix}/", 1)[1]
        target = local_processed / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        fs.get_file(remote, str(target))
        n += 1
    return n
