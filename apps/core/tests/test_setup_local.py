"""Tests de l'installateur guidé (setup_local.py) : fonctions pures uniquement (aucune base n'est créée ni supprimée)."""
import re
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import environ
from django.conf import settings
from django.test import SimpleTestCase

import setup_local as sl
from apps.core.tests.helpers import FIXTURE, rmtree


class GrantTests(SimpleTestCase):
    def test_underscores_are_escaped_so_the_php_database_is_out_of_reach(self):
        # `opti_cloud` non échappé couvrirait aussi la base PHP « opti cloud » (joker « _ » = n'importe quel caractère).
        self.assertEqual(sl.escape_grant_db("opti_cloud"), "opti\\_cloud")
        self.assertEqual(sl.escape_grant_db("test_opti_cloud_legacy"), "test\\_opti\\_cloud\\_legacy")
        self.assertEqual(sl.escape_grant_db("a%b"), "a\\%b")

    def test_every_generated_grant_targets_an_exact_database_name(self):
        statements = sl.grant_statements()
        self.assertEqual(len(statements), 4)
        for sql, _user in statements:
            db = re.search(r"ON `([^`]+)`\.\*", sql).group(1)
            self.assertNotRegex(db, r"(?<!\\)[_%]", f"joker non échappé dans {db}")

    def test_privileges_match_the_security_design(self):
        by_user = {}
        for sql, user in sl.grant_statements():
            by_user.setdefault(user, []).append(sql)
        self.assertEqual(len(by_user["opticloud"]), 3)
        self.assertTrue(all("ALL PRIVILEGES" in s for s in by_user["opticloud"]))
        self.assertFalse(any("legacy" in s and "test" not in s for s in by_user["opticloud"]), "aucun droit du compte d'écriture sur la copie legacy")
        self.assertEqual(len(by_user["opticloud_ro"]), 1)
        self.assertTrue(by_user["opticloud_ro"][0].startswith("GRANT SELECT ON"))
        self.assertFalse(any("opti cloud" in s.replace("\\_", " ") and "legacy" not in s and "test" not in s and "opti\\_cloud`" not in s for s in by_user["opticloud"]))

    def test_the_readme_manual_sql_also_escapes_underscores(self):
        readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")
        grants = [l for l in readme.splitlines() if l.startswith("GRANT")]
        self.assertGreaterEqual(len(grants), 4)
        for line in grants:
            db = re.search(r"ON `([^`]+)`\.\*", line).group(1)
            self.assertNotRegex(db, r"(?<!\\)[_%]", line)


class FakeCursor:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.cur = FakeCursor()

    def cursor(self):
        return self.cur


class AccountSetupTests(SimpleTestCase):
    def run_setup(self):
        conn = FakeConnection()
        sl.setup_database_and_users(conn, "pw-rw", "pw-ro")
        return [sql for sql, _ in conn.cur.statements], conn.cur.statements

    def test_old_privileges_are_wiped_before_the_right_ones_are_granted(self):
        sqls, statements = self.run_setup()
        for host in sl.HOSTS:
            for user in (sl.APP_USER, sl.RO_USER):
                revoke = [i for i, (sql, params) in enumerate(statements) if sql.startswith("REVOKE ALL") and params == (user, host)]
                grants = [i for i, (sql, params) in enumerate(statements) if sql.startswith("GRANT") and params == (user, host)]
                self.assertEqual(len(revoke), 1, (user, host))
                self.assertTrue(grants and max(0, min(grants)) > revoke[0], f"le REVOKE doit précéder les GRANT pour {user}@{host}")

    def test_passwords_are_sent_as_parameters_never_written_in_the_sql_text(self):
        sqls, statements = self.run_setup()
        self.assertFalse(any("pw-rw" in sql or "pw-ro" in sql for sql in sqls))
        self.assertTrue(any(params and "pw-rw" in params for _, params in statements))

    def test_both_databases_are_created_in_utf8mb4_and_everything_is_idempotent(self):
        sqls, _ = self.run_setup()
        self.assertEqual([s for s in sqls if s.startswith("CREATE DATABASE")],
                         [f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" for db in (sl.DJANGO_DB, sl.LEGACY_DB)])
        self.assertTrue(all("IF NOT EXISTS" in s for s in sqls if s.startswith("CREATE USER")))
        self.assertEqual(sqls[-1], "FLUSH PRIVILEGES")

    def test_nothing_is_ever_granted_on_the_php_database_or_globally(self):
        sqls, _ = self.run_setup()
        for sql in (s for s in sqls if s.startswith("GRANT")):
            self.assertNotIn("*.*", sql)
            self.assertNotIn("opti cloud", sql)
            self.assertNotIn("WITH GRANT OPTION", sql)


class EnvFileTests(SimpleTestCase):
    def test_generated_env_is_read_back_exactly_by_django_environ(self):
        text = sl.render_env(secret_key="k-_AbC123", db_port=3307, rw_password="pw-rw_1", ro_password="pw-ro_2", archive_dir=Path("C:/OptiCloud_Archives"))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text(text, encoding="utf-8")
            env = environ.Env()
            with mock.patch.dict("os.environ", {}, clear=False):
                for key in ("SECRET_KEY", "DB_PORT", "ARCHIVE_DIR", "PROTECTED_DATABASES", "DB_USER", "LEGACY_DB_USER"):
                    __import__("os").environ.pop(key, None)
                environ.Env.read_env(p, overwrite=True)
                self.assertEqual(env("SECRET_KEY"), "k-_AbC123")
                self.assertEqual(env("DB_PORT"), "3307")
                self.assertEqual(env("DB_USER"), "opticloud")
                self.assertEqual(env("LEGACY_DB_USER"), "opticloud_ro")
                self.assertEqual(env("ARCHIVE_DIR"), "C:/OptiCloud_Archives")
                self.assertEqual(env.list("PROTECTED_DATABASES"), ["opti cloud"])

    def test_generated_passwords_and_keys_use_only_safe_characters(self):
        import secrets
        for _ in range(200):
            self.assertRegex(secrets.token_urlsafe(18), r"^[A-Za-z0-9_-]+$")


class SecretsReuseTests(SimpleTestCase):
    GOOD = "SECRET_KEY='cle-existante'\nDB_USER=opticloud\nDB_PASSWORD=pw-rw\nLEGACY_DB_USER=opticloud_ro\nLEGACY_DB_PASSWORD=pw-ro\n"

    def test_parse_env_reads_values_and_ignores_comments_and_quotes(self):
        v = sl.parse_env("# commentaire\n\nSECRET_KEY='abc'\nA=1\nB=\"deux\"\nC = trois \nsans_egal\n")
        self.assertEqual(v, {"SECRET_KEY": "abc", "A": "1", "B": "deux", "C": "trois"})

    def test_a_configured_env_keeps_its_secrets_so_a_rerun_never_breaks_a_working_install(self):
        key, rw, ro, reused = sl.choose_secrets(sl.parse_env(self.GOOD))
        self.assertEqual((key, rw, ro, reused), ("cle-existante", "pw-rw", "pw-ro", True))

    def test_a_missing_or_foreign_env_gets_fresh_random_secrets(self):
        for text in ("", "DB_USER=root\nDB_PASSWORD=x\n", self.GOOD.replace("DB_PASSWORD=pw-rw\n", "")):
            key, rw, ro, reused = sl.choose_secrets(sl.parse_env(text))
            self.assertFalse(reused)
            self.assertNotEqual(rw, ro)
            self.assertGreaterEqual(len(rw), 20)

    def test_an_archive_folder_inside_the_project_is_refused_before_anything_else(self):
        with self.assertRaises(sl.SetupError):
            sl.check_archive_dir(sl.BASE / "archive")
        with self.assertRaises(sl.SetupError):
            sl.check_archive_dir(sl.BASE)
        sl.check_archive_dir(sl.BASE.parent / "OptiCloud_Archives")


class SourceFileTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="opticloud_setup_test_"))
        self.addCleanup(rmtree, self.tmp)

    def make_zip(self, members: dict, name="OPTI_CLOUD.zip") -> Path:
        z = self.tmp / name
        with zipfile.ZipFile(z, "w") as zf:
            for member, data in members.items():
                zf.writestr(member, data)
        return z

    def test_the_dump_is_found_in_the_nested_original_layout_and_copied_byte_for_byte(self):
        data = FIXTURE.read_bytes()
        z = self.make_zip({"OPTI CLOUD/connexion.php": b"<?php", "OPTI CLOUD/opti cloud.sql/opti cloud.sql": data})
        self.assertEqual(sl.find_sql_in_zip(z), "OPTI CLOUD/opti cloud.sql/opti cloud.sql")
        out = sl.extract_sql_from_zip(z, self.tmp)
        self.assertEqual(out.name, "opti cloud.sql")
        self.assertEqual(out.read_bytes(), data)
        self.assertEqual(sl.sha256_file(out), sl.sha256_file(FIXTURE))

    def test_the_zip_is_never_modified(self):
        z = self.make_zip({"a/opti cloud.sql": b"x"})
        before = sl.sha256_file(z)
        sl.extract_sql_from_zip(z, self.tmp)
        self.assertEqual(sl.sha256_file(z), before)

    def test_zip_without_or_with_several_dumps_is_refused(self):
        with self.assertRaises(sl.SetupError):
            sl.find_sql_in_zip(self.make_zip({"a.txt": b"x"}, "vide.zip"))
        with self.assertRaises(sl.SetupError):
            sl.find_sql_in_zip(self.make_zip({"a.sql": b"x", "b.sql": b"y"}, "deux.zip"))

    def test_resolve_source_accepts_a_file_a_quoted_path_or_a_folder(self):
        z = self.make_zip({"x.sql": b"x"})
        self.assertEqual(sl.resolve_source(str(z), True), z.resolve())
        self.assertEqual(sl.resolve_source(f'"{z}"', True), z.resolve())
        self.assertEqual(sl.resolve_source(str(self.tmp), True), z.resolve())
        with self.assertRaises(sl.SetupError):
            sl.resolve_source(str(self.tmp / "absent.zip"), True)

    def test_candidate_sources_finds_the_files_in_the_usual_places(self):
        project = self.tmp / "projet"
        project.mkdir()
        (self.tmp / "OPTI_CLOUD.zip").write_bytes(b"zip")                 # à côté du dossier du projet
        with mock.patch.object(sl, "BASE", project), mock.patch.object(Path, "home", return_value=self.tmp / "home"):
            self.assertIn((self.tmp / "OPTI_CLOUD.zip").resolve(), sl.candidate_sources())

    def test_an_already_archived_dump_is_recognised_by_its_hash(self):
        arch = self.tmp / "archive"
        snap = arch / "snapshot_20260101_000000"
        snap.mkdir(parents=True)
        (snap / "MANIFEST.sha256").write_text("abc123  opti cloud.sql\nfff  OPTI_CLOUD.zip\n", encoding="utf-8")
        self.assertEqual(sl.existing_snapshot_for(arch, "abc123"), snap)
        self.assertIsNone(sl.existing_snapshot_for(arch, "autre"))
        self.assertIsNone(sl.existing_snapshot_for(self.tmp / "inexistant", "abc123"))

    def test_the_default_archive_folder_is_outside_the_project(self):
        d = sl.default_archive_dir()
        self.assertNotEqual(d, sl.BASE)
        self.assertNotIn(sl.BASE, d.parents)


class BatchFileTests(SimpleTestCase):
    def read(self, name):
        return (Path(settings.BASE_DIR) / name).read_bytes()

    def test_batch_files_are_plain_ascii_with_windows_line_endings(self):
        for name in ("INSTALLER_ET_LANCER.bat", "LANCER_OPTI_CLOUD.bat"):
            data = self.read(name)
            data.decode("ascii")
            self.assertIn(b"\r\n", data, name)
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""), f"{name} : fin de ligne sans retour chariot")

    def test_the_installer_runs_the_guided_setup_then_the_server(self):
        text = self.read("INSTALLER_ET_LANCER.bat").decode("ascii")
        for expected in ("python -m venv .venv", "pip install -r requirements.txt", "python setup_local.py", "python manage.py runserver", "http://127.0.0.1:8000/"):
            self.assertIn(expected, text)
        self.assertLess(text.index("setup_local.py"), text.index("runserver"))

    def test_the_launcher_refuses_to_start_without_installation(self):
        text = self.read("LANCER_OPTI_CLOUD.bat").decode("ascii")
        self.assertIn('if not exist ".env"', text)
        self.assertIn("python manage.py runserver", text)
