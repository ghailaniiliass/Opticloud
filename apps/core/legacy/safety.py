"""
Garde-fous de la migration.

Objectif : `import_legacy` ne peut agir QUE sur la base Django. Il refuse toute opération visant la base PHP
d'origine, la copie de travail `opti_cloud_legacy` ou une base système.
La protection la plus forte reste côté MySQL : le compte `opticloud` n'a aucun droit sur ces bases.
"""
from __future__ import annotations

from .registry import MODEL_APP_LABELS

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", ""}
SYSTEM_DATABASES = {"mysql", "sys", "information_schema", "performance_schema", "phpmyadmin", "test"}


class SafetyError(Exception):
    pass


def protected_names(legacy_name: str, extra: list[str] | None) -> set[str]:
    names = {n.lower() for n in SYSTEM_DATABASES}
    names.add((legacy_name or "").lower())
    names.update(n.lower() for n in (extra or []))
    names.discard("")
    return names


def assert_safe_config(default_cfg: dict, legacy_cfg: dict, extra_protected: list[str] | None) -> None:
    """Contrôles exécutés à CHAQUE lancement de `import_legacy`, simulation comprise."""
    target = (default_cfg.get("NAME") or "")
    legacy = (legacy_cfg.get("NAME") or "")
    if not target:
        raise SafetyError("Aucune base cible configurée (DB_NAME).")
    if "mysql" not in default_cfg.get("ENGINE", ""):
        raise SafetyError("La base cible doit être MySQL (pas de SQLite).")
    if target.lower() == legacy.lower():
        raise SafetyError(
            f"DB_NAME ({target!r}) est identique à LEGACY_DB_NAME : la base cible ne peut pas être la copie du dump d'origine."
        )
    if target.lower() in protected_names(legacy, extra_protected):
        raise SafetyError(
            f"La base {target!r} est PROTÉGÉE (base PHP d'origine, copie legacy ou base système) : opération refusée."
        )
    for label, cfg in (("cible", default_cfg), ("legacy", legacy_cfg)):
        host = (cfg.get("HOST") or "").lower()
        if host not in LOCAL_HOSTS:
            raise SafetyError(f"Le serveur de la base {label} ({host}) n'est pas local : opération refusée (phase locale uniquement).")


def assert_reset_allowed(default_cfg: dict, legacy_cfg: dict, confirm: str | None, extra_protected: list[str] | None) -> None:
    assert_safe_config(default_cfg, legacy_cfg, extra_protected)
    target = default_cfg.get("NAME")
    if not confirm:
        raise SafetyError(
            "--reset exige --confirm-database avec le nom EXACT de la base cible. "
            f"Exemple : python manage.py import_legacy --reset --confirm-database {target}"
        )
    if confirm != target:
        raise SafetyError(
            f"--confirm-database {confirm!r} ne correspond pas à la base cible configurée {target!r} : --reset refusé."
        )


def target_is_django_db(connection) -> bool:
    """Vrai seulement si la base contient `django_migrations` avec toutes les applications du projet appliquées.
    La base PHP d'origine et la copie legacy n'ont jamais cette signature."""
    with connection.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'django_migrations'")
        if cur.fetchone() is None:
            return False
        marks = ", ".join(["%s"] * len(MODEL_APP_LABELS))
        cur.execute(f"SELECT COUNT(DISTINCT app) FROM django_migrations WHERE app IN ({marks})", MODEL_APP_LABELS)
        return cur.fetchone()[0] == len(MODEL_APP_LABELS)
