import os
import stat
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.core.legacy import archive
from apps.core.tests.helpers import rmtree


def _writable(p: Path) -> bool:
    return bool(stat.S_IMODE(os.stat(p).st_mode) & 0o222)


class ArchiveTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="opticloud_arch_"))
        self.addCleanup(rmtree, self.tmp)
        self.src = self.tmp / "originaux"
        self.src.mkdir()
        self.dump = self.src / "opti cloud.sql"
        self.dump.write_bytes("INSERT 'é';\n".encode("utf-8"))
        self.zip = self.src / "OPTI_CLOUD.zip"
        self.zip.write_bytes(b"PK\x03\x04 contenu zip")
        self.arch = self.tmp / "archive"

    def backup(self, **kw):
        opts = {"dump": str(self.dump), "zip": str(self.zip), "archive_dir": str(self.arch), "verify": False, "snapshot": None}
        opts.update(kw)
        out = StringIO()
        call_command("backup_dump", stdout=out, **opts)
        return out.getvalue()

    def snapshot(self) -> Path:
        return sorted(p for p in self.arch.iterdir() if p.is_dir())[-1]

    def test_sha256_known_value(self):
        p = self.tmp / "abc.txt"
        p.write_bytes(b"abc")
        self.assertEqual(archive.sha256_file(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_snapshot_has_copies_manifest_and_everything_is_read_only(self):
        self.backup()
        snap = self.snapshot()
        names = sorted(p.name for p in snap.iterdir())
        self.assertEqual(names, ["MANIFEST.sha256", "OPTI_CLOUD.zip", "opti cloud.sql"])
        manifest = archive.read_manifest(snap)
        self.assertEqual(manifest["opti cloud.sql"], archive.sha256_file(self.dump))
        self.assertEqual(manifest["OPTI_CLOUD.zip"], archive.sha256_file(self.zip))
        for p in snap.iterdir():
            self.assertFalse(_writable(p), f"{p.name} doit être en lecture seule")

    def test_manifest_is_in_standard_sha256sum_format(self):
        self.backup()
        line = (self.snapshot() / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()[0]
        digest, sep, name = line.partition("  ")
        self.assertEqual((len(digest), sep, name), (64, "  ", "opti cloud.sql"))

    def test_original_files_are_never_modified(self):
        before = {p: (archive.sha256_file(p), p.stat().st_mtime_ns, p.stat().st_mode) for p in (self.dump, self.zip)}
        self.backup()
        self.backup(archive_dir=str(self.tmp / "archive2"))
        for p, snapshot in before.items():
            self.assertEqual((archive.sha256_file(p), p.stat().st_mtime_ns, p.stat().st_mode), snapshot)

    def test_archive_inside_the_project_is_refused(self):
        inside = Path(settings.BASE_DIR) / "archive_interdite"
        with self.assertRaisesMessage(CommandError, "DANS le projet"):
            self.backup(archive_dir=str(inside))
        self.assertFalse(inside.exists(), "le dossier interdit ne doit pas être créé")

    def test_project_root_itself_is_refused(self):
        with self.assertRaisesMessage(CommandError, "DANS le projet"):
            self.backup(archive_dir=str(settings.BASE_DIR))

    @override_settings(ARCHIVE_DIR="")
    def test_no_archive_directory_configured(self):
        with self.assertRaisesMessage(CommandError, "ARCHIVE_DIR"):
            self.backup(archive_dir=None)

    def test_missing_or_non_sql_source_is_refused(self):
        with self.assertRaisesMessage(CommandError, "introuvable"):
            self.backup(dump=str(self.src / "absent.sql"))
        with self.assertRaisesMessage(CommandError, ".sql"):
            self.backup(dump=str(self.zip), zip=None)
        self.assertFalse(self.arch.exists() and any(self.arch.iterdir()))

    def test_source_already_in_archive_is_refused(self):
        self.backup()
        copy = self.snapshot() / "opti cloud.sql"
        with self.assertRaisesMessage(CommandError, "déjà dans le dossier d'archive"):
            self.backup(dump=str(copy), zip=None)

    def test_a_snapshot_is_never_overwritten(self):
        with mock.patch.object(archive, "snapshot_name", return_value="snapshot_fixe"):
            self.backup()
            snap = self.arch / "snapshot_fixe"
            sha = archive.sha256_file(snap / "opti cloud.sql")
            self.dump.write_bytes(b"autre contenu")
            with self.assertRaisesMessage(CommandError, "existe déjà"):
                self.backup()
        self.assertEqual(archive.sha256_file(snap / "opti cloud.sql"), sha)

    def test_verify_passes_then_detects_tampering(self):
        self.backup()
        out = StringIO()
        call_command("backup_dump", verify=True, archive_dir=str(self.arch), snapshot=None, dump=None, zip=None, stdout=out)
        self.assertIn("Archive intacte", out.getvalue())
        victim = self.snapshot() / "opti cloud.sql"
        victim.chmod(0o644)
        victim.write_bytes(victim.read_bytes() + b" ")
        with self.assertRaisesMessage(CommandError, "ne correspond plus"):
            call_command("backup_dump", verify=True, archive_dir=str(self.arch), snapshot=None, dump=None, zip=None, stdout=StringIO())

    def test_verify_reports_a_deleted_file(self):
        self.backup()
        (self.snapshot() / "OPTI_CLOUD.zip").unlink()
        results = {r["name"]: r for r in archive.verify_snapshot(self.snapshot())}
        self.assertFalse(results["OPTI_CLOUD.zip"]["ok"])
        self.assertTrue(results["opti cloud.sql"]["ok"])

    def test_latest_snapshot_is_selected_by_default(self):
        with mock.patch.object(archive, "snapshot_name", side_effect=["snapshot_20260101_000000", "snapshot_20260102_000000"]):
            self.backup()
            self.backup()
        self.assertEqual(archive.resolve_snapshot(self.arch, None).name, "snapshot_20260102_000000")
