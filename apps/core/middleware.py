"""Middleware léger activé uniquement sur Vercel en mode aperçu (SQLite /tmp) tant qu'aucune base MySQL cloud n'est configurée."""
import os
import threading
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

_init_lock = threading.Lock()
_initialized_path: str | None = None


def _seed_demo_data_if_empty() -> None:
    from apps.core.legacy.dumpparser import parse_dump_file
    from apps.core.legacy.registry import get_model

    fixture = Path(__file__).resolve().parent / "tests" / "fixtures" / "mini_dump.sql"
    if not fixture.is_file():
        return
    dump = parse_dump_file(fixture)
    for tname, table in dump.tables.items():
        model = get_model(tname)
        if model.objects.exists():
            continue
        objs = [model(**dict(zip(table.column_names, row))) for row in table.typed_rows()]
        if objs:
            model.objects.bulk_create(objs)


class VercelDemoDatabaseMiddleware:
    """Si VERCEL=1 utilise le repli SQLite dans /tmp, initialise les tables et le jeu de démo au premier appel HTTP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _initialized_path
        if os.environ.get("VERCEL") == "1" and not getattr(settings, "TESTING", False):
            default_db = settings.DATABASES.get("default", {})
            db_path = str(default_db.get("NAME", ""))
            if default_db.get("ENGINE") == "django.db.backends.sqlite3" and db_path:
                if _initialized_path != db_path or not os.path.exists(db_path):
                    with _init_lock:
                        if _initialized_path != db_path or not os.path.exists(db_path):
                            call_command("migrate", "--noinput", verbosity=0)
                            _seed_demo_data_if_empty()
                            _initialized_path = db_path
        return self.get_response(request)
