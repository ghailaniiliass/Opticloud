"""Outils communs aux tests de migration. Toutes les données utilisées sont FICTIVES (fixtures/mini_dump.sql)."""
import os
import shutil
import stat
import tempfile
import warnings
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase

from apps.core.legacy.dumpparser import split_statements
from apps.core.legacy.registry import LEGACY_TABLES, get_model

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dump.sql"
EXPECTED_COUNTS = {"categorie": 3, "client": 0, "fournisseur": 3, "lentille": 2, "marque": 4,
                   "monture": 3, "ordonnance": 2, "patient": 3, "verre": 2}
DUMP_NAME = "opti cloud.sql"


def fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _rm_readonly(func, path, exc):
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    func(path)


def rmtree(path):
    shutil.rmtree(path, onexc=_rm_readonly)


def load_into_legacy(sql_text: str) -> None:
    """Charge un dump dans la copie de travail (comme le fera phpMyAdmin) après avoir supprimé les 9 tables."""
    with connections["legacy"].cursor() as cur, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for t in list(LEGACY_TABLES) + ["autre"]:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        for stmt in split_statements(sql_text):
            cur.execute(stmt)


def legacy_execute(sql: str) -> None:
    with connections["legacy"].cursor() as cur, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cur.execute(sql)


def make_snapshot(tmp: Path, sql_text: str, with_zip: bool = False):
    src = tmp / "originaux"
    src.mkdir(exist_ok=True)
    dump = src / DUMP_NAME
    dump.write_text(sql_text, encoding="utf-8", newline="\n")
    kwargs = {"dump": str(dump), "archive_dir": str(tmp / "archive"), "zip": None, "verify": False, "snapshot": None}
    if with_zip:
        z = src / "OPTI_CLOUD.zip"
        z.write_bytes(b"PK-fake-zip-content")
        kwargs["zip"] = str(z)
    call_command("backup_dump", stdout=StringIO(), **kwargs)
    archive_dir = tmp / "archive"
    snapshot = sorted(p for p in archive_dir.iterdir() if p.is_dir())[-1]
    return archive_dir, snapshot, dump


def reset_auto_increment_counters() -> None:
    """Django vide les tables entre deux tests avec DELETE : les compteurs AUTO_INCREMENT persistent.
    On les remet à 1 pour que chaque test soit indépendant de l'ordre d'exécution."""
    with connections["default"].cursor() as cur:
        for table in ("fournisseur", "monture", "patient", "ordonnance"):
            cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1")


def count_all() -> dict:
    return {t: get_model(t).objects.count() for t in LEGACY_TABLES}


class MigrationTestBase(TransactionTestCase):
    """Prépare : copie legacy chargée avec le mini-dump + snapshot d'archive dans un dossier temporaire HORS projet."""

    databases = {"default", "legacy"}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="opticloud_test_"))
        self.addCleanup(rmtree, self.tmp)
        self.report_dir = self.tmp / "reports"
        reset_auto_increment_counters()
        load_into_legacy(fixture_text())
        self.archive_dir, self.snapshot, self.source_dump = make_snapshot(self.tmp, fixture_text())
        self.out, self.err = StringIO(), StringIO()

    @property
    def target_name(self) -> str:
        return connections["default"].settings_dict["NAME"]

    def run_cmd(self, **options):
        self.out, self.err = StringIO(), StringIO()
        options.setdefault("archive_dir", str(self.archive_dir))
        options.setdefault("report_dir", str(self.report_dir))
        call_command("import_legacy", stdout=self.out, stderr=self.err, **options)
        return self.out.getvalue()

    def report_json(self, name="migration_report.json") -> dict:
        import json
        return json.loads((self.report_dir / name).read_text(encoding="utf-8"))
