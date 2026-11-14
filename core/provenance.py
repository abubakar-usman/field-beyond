"""Provenance helpers: checksums, code version, config hashes (CLAUDE.md rule 6)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def config_hash(paths: Iterable[str | Path]) -> str:
    """Hash of several config files, independent of argument order.

    Each file contributes its name and its raw bytes, so a whitespace edit is a
    change. That is intended: released config files are never edited in place.
    """
    h = hashlib.sha256()
    for p in sorted(Path(x) for x in paths):
        h.update(p.name.encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def stable_json_hash(obj: Any) -> str:
    return sha256_bytes(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    )


def git_sha(repo_dir: str | Path | None = None) -> str:
    """Code version. `GIT_SHA` (set at image build) wins, then git, then 'unknown'."""
    env = os.environ.get("GIT_SHA")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir or Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sha = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir or Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@dataclass
class Provenance:
    """Attached to everything derived."""

    code_version: str
    config_hash: str
    schema_version: str
    source_asset_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
