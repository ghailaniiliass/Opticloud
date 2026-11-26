"""
Archive des originaux (ZIP + dump) : HORS du projet, en lecture seule, avec empreintes SHA-256.

Règles :
  * les fichiers d'origine ne sont jamais ouverts autrement qu'en lecture ;
  * un snapshot n'est jamais écrasé ;
  * le dossier d'archive ne peut pas se trouver dans le projet.
"""
from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime
from pathlib import Path

from django.conf import settings

MANIFEST_NAME = "MANIFEST.sha256"


class ArchiveError(Exception):
    pass


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_archive_dir(value: str | None) -> Path:
    value = value or getattr(settings, "ARCHIVE_DIR", "")
    if not value:
        raise ArchiveError("Aucun dossier d'archive : renseignez ARCHIVE_DIR dans le .env ou passez --archive-dir.")
    path = Path(value).expanduser().resolve()
    base = Path(settings.BASE_DIR).resolve()
    if path == base or _is_relative_to(path, base):
        raise ArchiveError(
            f"Le dossier d'archive ({path}) se trouve DANS le projet ({base}). "
            "Les originaux doivent être conservés hors du projet."
        )
    return path


def snapshot_name() -> str:
    return "snapshot_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def make_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def write_manifest(snapshot_dir: Path, entries: list[tuple[str, str]]) -> Path:
    manifest = snapshot_dir / MANIFEST_NAME
    manifest.write_text("".join(f"{h}  {name}\n" for h, name in entries), encoding="utf-8", newline="\n")
    make_readonly(manifest)
    return manifest


def read_manifest(snapshot_dir: Path) -> dict[str, str]:
    manifest = snapshot_dir / MANIFEST_NAME
    if not manifest.is_file():
        raise ArchiveError(f"Manifeste introuvable : {manifest}")
    out: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, _, name = line.partition("  ")
            out[name] = h
    return out


def verify_snapshot(snapshot_dir: Path) -> list[dict]:
    """Compare chaque fichier du manifeste à son empreinte actuelle."""
    results = []
    for name, expected in read_manifest(snapshot_dir).items():
        f = snapshot_dir / name
        actual = sha256_file(f) if f.is_file() else None
        results.append({"name": name, "expected": expected, "actual": actual, "ok": actual == expected})
    return results


def list_snapshots(archive_dir: Path) -> list[Path]:
    if not archive_dir.is_dir():
        return []
    return sorted(p for p in archive_dir.iterdir() if p.is_dir() and p.name.startswith("snapshot_"))


def resolve_snapshot(archive_dir: Path, name: str | None) -> Path:
    if name:
        p = archive_dir / name
        if not p.is_dir():
            raise ArchiveError(f"Snapshot introuvable : {p}")
        return p
    snaps = list_snapshots(archive_dir)
    if not snaps:
        raise ArchiveError(f"Aucun snapshot dans {archive_dir}. Lancez d'abord : python manage.py backup_dump --dump ...")
    return snaps[-1]


def dump_file_of(snapshot_dir: Path) -> Path:
    sqls = [n for n in read_manifest(snapshot_dir) if n.lower().endswith(".sql")]
    if len(sqls) != 1:
        raise ArchiveError(f"Le snapshot doit contenir exactement un fichier .sql (trouvé : {len(sqls)}).")
    return snapshot_dir / sqls[0]
