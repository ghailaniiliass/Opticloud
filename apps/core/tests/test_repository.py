"""Hygiène du dépôt GitHub : aucun secret, aucune donnée réelle, aucun original ne doit pouvoir être publié par erreur."""
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
GIT = shutil.which("git")


def tracked_files() -> list[str]:
    out = subprocess.run([GIT, "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


class GitignoreTests(SimpleTestCase):
    def lines(self):
        return {l.strip() for l in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}

    def test_sensitive_files_are_ignored(self):
        for pattern in (".env", ".env.bak-*", "docs/migration_report*", "*.sql", "*.zip", ".venv/", "__pycache__/"):
            self.assertIn(pattern, self.lines(), f"{pattern} doit être dans .gitignore")

    def test_only_the_fictional_test_dump_is_allowed_among_sql_files(self):
        self.assertIn("!apps/core/tests/fixtures/*.sql", self.lines())
        self.assertEqual([p.name for p in ROOT.glob("apps/core/tests/fixtures/*.sql")], ["mini_dump.sql"])

    def test_env_example_contains_no_real_secret(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        for placeholder in ("MotDePasseRW", "MotDePasseRO", "remplacez-par-une-cle-aleatoire"):
            self.assertIn(placeholder, text)


class GitAttributesTests(SimpleTestCase):
    def test_windows_batch_files_keep_crlf_and_binaries_are_untouched(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.bat text eol=crlf", text)
        self.assertIn("*.ttf binary", text)


class WorkflowTests(SimpleTestCase):
    def test_ci_runs_the_tests_against_a_real_mysql_and_never_with_real_secrets(self):
        text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        for expected in ("mysql:8.0", "python manage.py test", "makemigrations --check", "poppler-utils", "python-version: \"3.12\""):
            self.assertIn(expected, text)
        self.assertNotIn("sqlite", text.lower())
        self.assertNotIn("secrets.", text, "aucun secret GitHub n'est nécessaire")
        self.assertNotIn("libmysqlclient-dev", text, "PyMySQL ne nécessite aucune compilation C")


class TrackedFilesTests(SimpleTestCase):
    """Ne s'exécute que dans un dépôt Git (GitHub Actions, ou après `git init`)."""

    def setUp(self):
        if not GIT or not (ROOT / ".git").exists():
            self.skipTest("pas de dépôt Git ici (le test s'exécute après `git init`, et sur GitHub Actions)")

    def test_no_secret_dump_archive_or_real_report_is_tracked(self):
        files = tracked_files()
        self.assertTrue(files)
        forbidden = [f for f in files if Path(f).name == ".env" or Path(f).name.startswith(".env.bak")
                     or (f.endswith(".sql") and f != "apps/core/tests/fixtures/mini_dump.sql")
                     or f.endswith((".zip", ".pyc")) or f.startswith(("docs/migration_report", ".venv/"))]
        self.assertEqual(forbidden, [])

    def test_the_tracked_project_files_are_present(self):
        files = set(tracked_files())
        for expected in ("manage.py", "requirements.txt", ".env.example", ".gitignore", ".gitattributes", "README.md", "setup_local.py",
                         "INSTALLER_ET_LANCER.bat", "LANCER_OPTI_CLOUD.bat", ".github/workflows/tests.yml", "vercel.json", ".python-version",
                         "apps/core/fonts/LiberationSans-Regular.ttf"):
            self.assertIn(expected, files)
