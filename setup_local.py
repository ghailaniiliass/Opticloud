#!/usr/bin/env python
"""
Installation locale guidée d'Opti Cloud (Windows + WAMP, ou tout MySQL / MariaDB local).

Ce script fait, en une fois, tout ce qui était manuel dans le README :
  1. se connecte à MySQL avec le compte administrateur (« root » sous WAMP) et repère le bon port ;
  2. crée les bases `opti_cloud` (Django) et `opti_cloud_legacy` (copie de travail du dump) ;
  3. crée deux comptes dédiés aux mots de passe aléatoires : `opticloud` (écriture, base Django seulement)
     et `opticloud_ro` (lecture seule sur la copie du dump) ; ils n'ont AUCUN droit sur votre base PHP « opti cloud » ;
  4. écrit le fichier `.env` (clé secrète et mots de passe générés ; l'ancien `.env` est sauvegardé) ;
  5. archive vos originaux (ZIP + dump) HORS du projet, en lecture seule, avec empreintes SHA-256 ;
  6. charge le dump dans la copie de travail, crée le schéma Django, puis importe vos données avec vérification complète.

Vos fichiers d'origine et votre base PHP ne sont jamais modifiés. Relançable sans risque.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
PHP_DATABASE = "opti cloud"                  # nom de la base de l'application PHP d'origine (voir connexion.php) : jamais touchée
DJANGO_DB, LEGACY_DB = "opti_cloud", "opti_cloud_legacy"
APP_USER, RO_USER = "opticloud", "opticloud_ro"
HOSTS = ("localhost", "127.0.0.1")
PORTS_TO_TRY = (3306, 3307, 3308)            # WAMP : 3306 pour le serveur par défaut, 3307 ou 3308 pour l'autre
TABLES = ("categorie", "client", "fournisseur", "lentille", "marque", "monture", "ordonnance", "patient", "verre")
TOTAL_STEPS = 7


# ----------------------------------------------------------------------------------------------------------------
# Affichage
# ----------------------------------------------------------------------------------------------------------------
class SetupError(Exception):
    pass


def step(n: int, text: str) -> None:
    print(f"\n[{n}/{TOTAL_STEPS}] {text}")


def ok(text: str) -> None:
    print(f"      OK  {text}")


def info(text: str) -> None:
    print(f"          {text}")


# ----------------------------------------------------------------------------------------------------------------
# Fonctions pures (testées automatiquement)
# ----------------------------------------------------------------------------------------------------------------
def escape_grant_db(name: str) -> str:
    """Dans un GRANT, « _ » et « % » sont des jokers : `opti_cloud` couvrirait aussi une base nommée `opti cloud`
    (la base PHP !). On les échappe pour que le droit ne vise que le nom exact."""
    return name.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")


def grant_statements() -> list[tuple[str, str]]:
    """Droits accordés à chaque compte et pour chaque hôte (le texte contient %s %s : compte puis hôte)."""
    rw = [DJANGO_DB, "test_" + DJANGO_DB, "test_" + LEGACY_DB]      # les deux dernières : bases temporaires des tests automatiques
    statements = [(f"GRANT ALL PRIVILEGES ON `{escape_grant_db(db)}`.* TO %s@%s", APP_USER) for db in rw]
    statements.append((f"GRANT SELECT ON `{escape_grant_db(LEGACY_DB)}`.* TO %s@%s", RO_USER))
    return statements


def render_env(*, secret_key: str, db_port: int, rw_password: str, ro_password: str, archive_dir: Path) -> str:
    return f"""# Fichier généré par setup_local.py le {datetime.datetime.now():%d/%m/%Y à %H:%M}. Ne le partagez pas : il contient vos mots de passe.
SECRET_KEY='{secret_key}'
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# --- Base Django (compte lecture/écriture) ---
DB_NAME={DJANGO_DB}
DB_USER={APP_USER}
DB_PASSWORD={rw_password}
DB_HOST=127.0.0.1
DB_PORT={db_port}

# --- Copie de travail du dump (compte LECTURE SEULE) ---
LEGACY_DB_NAME={LEGACY_DB}
LEGACY_DB_USER={RO_USER}
LEGACY_DB_PASSWORD={ro_password}

# --- Archive des originaux : dossier HORS du projet ---
ARCHIVE_DIR={archive_dir.as_posix()}

# --- Bases que la migration refuse de toucher (séparées par des virgules) ---
PROTECTED_DATABASES={PHP_DATABASE}
"""


def parse_env(text: str) -> dict[str, str]:
    """Lit les lignes CLÉ=valeur d'un fichier .env (guillemets simples ou doubles retirés, commentaires ignorés)."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def choose_secrets(existing: dict[str, str]) -> tuple[str, str, str, bool]:
    """(clé secrète, mot de passe écriture, mot de passe lecture seule, réutilisés ?).
    Un .env déjà configuré pour ces comptes garde ses secrets : relancer l'installation ne casse jamais une installation qui fonctionne."""
    if (existing.get("DB_USER") == APP_USER and existing.get("DB_PASSWORD") and existing.get("LEGACY_DB_USER") == RO_USER
            and existing.get("LEGACY_DB_PASSWORD") and existing.get("SECRET_KEY")):
        return existing["SECRET_KEY"], existing["DB_PASSWORD"], existing["LEGACY_DB_PASSWORD"], True
    return secrets.token_urlsafe(50), secrets.token_urlsafe(18), secrets.token_urlsafe(18), False


def check_archive_dir(archive_dir: Path) -> None:
    if archive_dir == BASE or BASE in archive_dir.parents:
        raise SetupError(f"Le dossier d'archive ({archive_dir}) est dans le projet : choisissez un dossier HORS du projet.")


def find_sql_in_zip(zip_path: Path) -> str:
    """Nom, dans le ZIP, du fichier dump .sql (le seul fichier .sql du ZIP)."""
    with zipfile.ZipFile(zip_path) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(".sql")]
    if not names:
        raise SetupError(f"Aucun fichier .sql dans {zip_path}.")
    if len(names) > 1:
        raise SetupError(f"Plusieurs fichiers .sql dans {zip_path} : {names}. Indiquez directement le bon dump avec --source.")
    return names[0]


def extract_sql_from_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Copie le dump du ZIP vers dest_dir/« opti cloud.sql » (octets identiques ; le ZIP n'est jamais modifié)."""
    member = find_sql_in_zip(zip_path)
    target = dest_dir / "opti cloud.sql"
    with zipfile.ZipFile(zip_path) as z, z.open(member) as src, open(target, "wb") as out:
        shutil.copyfileobj(src, out)
    return target


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_sources() -> list[Path]:
    """Endroits habituels où se trouvent OPTI_CLOUD.zip ou « opti cloud.sql »."""
    home = Path.home()
    folders = [BASE, BASE.parent, Path.cwd(), home / "Downloads", home / "Téléchargements", home / "Desktop", home / "Bureau", home / "Documents"]
    found, seen = [], set()
    for folder in folders:
        for name in ("OPTI_CLOUD.zip", "opti cloud.sql"):
            p = folder / name
            if p.is_file() and p.resolve() not in seen:
                seen.add(p.resolve())
                found.append(p.resolve())
    return found


def existing_snapshot_for(archive_dir: Path, sql_sha: str) -> Path | None:
    """Snapshot déjà archivé contenant ce même dump (pour ne pas en créer un nouveau à chaque exécution)."""
    if not archive_dir.is_dir():
        return None
    for snap in sorted(archive_dir.glob("snapshot_*"), reverse=True):
        manifest = snap / "MANIFEST.sha256"
        if manifest.is_file() and any(line.startswith(sql_sha + "  ") and line.strip().endswith(".sql")
                                      for line in manifest.read_text(encoding="utf-8").splitlines()):
            return snap
    return None


def default_archive_dir() -> Path:
    return (BASE.parent / "OptiCloud_Archives").resolve()


# ----------------------------------------------------------------------------------------------------------------
# MySQL
# ----------------------------------------------------------------------------------------------------------------
def connect(host: str, port: int, user: str, password: str, db: str = ""):
    import MySQLdb
    return MySQLdb.connect(host=host, port=port, user=user, passwd=password, db=db, charset="utf8mb4", connect_timeout=5)


def connect_admin(host: str, port: int | None, user: str, password: str):
    import MySQLdb
    ports = (port,) if port else PORTS_TO_TRY
    last_error = None
    for p in ports:
        try:
            conn = connect(host, p, user, password)
            return conn, p
        except MySQLdb.OperationalError as exc:
            last_error = exc
            if exc.args and exc.args[0] == 1045:                # accès refusé : le serveur répond, mais le mot de passe est faux
                raise SetupError(
                    f"MySQL (port {p}) refuse le compte « {user} » : mot de passe incorrect. Sous WAMP, le mot de passe de « root » est vide par défaut."
                ) from exc
    raise SetupError(
        f"Impossible de se connecter à MySQL sur {host} (ports essayés : {', '.join(map(str, ports))}).\n"
        "      Vérifiez que WAMP est démarré (icône VERTE) puis relancez. Dernier message : " + str(last_error)
    )


def setup_database_and_users(conn, rw_password: str, ro_password: str) -> None:
    cur = conn.cursor()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for db in (DJANGO_DB, LEGACY_DB):
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        for user, password in ((APP_USER, rw_password), (RO_USER, ro_password)):
            for host in HOSTS:
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (user, host, password))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (user, host, password))      # un compte déjà existant reçoit le mot de passe du .env
                # Table rase des droits : un ancien GRANT trop large (par exemple `opti_cloud` non échappé, qui couvrait aussi la base PHP
                # « opti cloud ») ne doit jamais survivre ; les bons droits sont ré-accordés juste après.
                cur.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@%s", (user, host))
        for sql, user in grant_statements():
            for host in HOSTS:
                cur.execute(sql, (user, host))
        cur.execute("FLUSH PRIVILEGES")


def check_php_database_is_out_of_reach(host: str, port: int, rw_password: str, ro_password: str, admin_conn) -> str:
    """Vérifie réellement que les comptes de l'application ne peuvent rien lire dans la base PHP d'origine."""
    import MySQLdb
    cur = admin_conn.cursor()
    cur.execute("SHOW DATABASES LIKE %s", (PHP_DATABASE,))
    if cur.fetchone() is None:
        return "la base PHP « opti cloud » n'existe pas sur ce serveur (rien à protéger)"
    cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s LIMIT 1", (PHP_DATABASE,))
    row = cur.fetchone()
    for user, password in ((APP_USER, rw_password), (RO_USER, ro_password)):
        c = connect(host, port, user, password)
        k = c.cursor()
        k.execute("SHOW DATABASES")
        if PHP_DATABASE in {r[0] for r in k.fetchall()}:
            raise SetupError(f"Le compte « {user} » voit la base PHP « {PHP_DATABASE} » : droits trop larges, installation arrêtée.")
        if row:
            try:
                k.execute(f"SELECT 1 FROM `{PHP_DATABASE}`.`{row[0]}` LIMIT 1")
            except MySQLdb.Error:
                pass
            else:
                raise SetupError(f"Le compte « {user} » peut lire la base PHP « {PHP_DATABASE} » : droits trop larges, installation arrêtée.")
        c.close()
    return "les comptes de l'application ne voient pas la base PHP « opti cloud » (vérifié)"


def load_dump_into_legacy(host: str, port: int, user: str, password: str, sql_path: Path) -> dict[str, int]:
    """Charge le dump (UTF-8) dans la copie de travail, comme le ferait phpMyAdmin avec « jeu de caractères du fichier : utf-8 »."""
    sys.path.insert(0, str(BASE))
    from apps.core.legacy.dumpparser import parse_dump_file, split_statements
    dump = parse_dump_file(sql_path)                        # refuse un fichier qui n'est pas de l'UTF-8 valide
    expected = dump.row_counts()
    conn = connect(host, port, user, password, db=LEGACY_DB)
    cur = conn.cursor()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for table in list(dump.tables):
            cur.execute(f"DROP TABLE IF EXISTS `{table}`")      # la copie de travail est jetable : on repart d'un état propre
        for stmt in split_statements(sql_path.read_text(encoding="utf-8")):
            cur.execute(stmt)
    conn.commit()
    loaded = {}
    for table, n in expected.items():
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        loaded[table] = cur.fetchone()[0]
        if loaded[table] != n:
            raise SetupError(f"Chargement incomplet de « {table} » : {loaded[table]} ligne(s) au lieu de {n}.")
    conn.close()
    return loaded


def django_target_row_count(host: str, port: int, user: str, password: str) -> int:
    conn = connect(host, port, user, password, db=DJANGO_DB)
    cur = conn.cursor()
    total = 0
    for table in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        total += cur.fetchone()[0]
    conn.close()
    return total


# ----------------------------------------------------------------------------------------------------------------
# Programme principal
# ----------------------------------------------------------------------------------------------------------------
def manage(*args: str) -> None:
    result = subprocess.run([sys.executable, "manage.py", *args], cwd=BASE)
    if result.returncode != 0:
        raise SetupError(f"La commande « manage.py {' '.join(args)} » a échoué (voir le message ci-dessus).")


def resolve_source(arg: str | None, yes: bool) -> Path:
    if arg:
        path = Path(arg.strip('"')).expanduser()
        if path.is_dir():
            for name in ("OPTI_CLOUD.zip", "opti cloud.sql"):
                if (path / name).is_file():
                    return (path / name).resolve()
            raise SetupError(f"Ni OPTI_CLOUD.zip ni « opti cloud.sql » dans {path}.")
        if not path.is_file():
            raise SetupError(f"Fichier introuvable : {path}")
        return path.resolve()
    candidates = candidate_sources()
    if len(candidates) >= 1 and (yes or len(candidates) == 1):
        info(f"fichier trouvé automatiquement : {candidates[0]}")
        return candidates[0]
    if candidates:
        print("      Plusieurs fichiers trouvés :")
        for i, c in enumerate(candidates, 1):
            print(f"        {i}. {c}")
        choice = input("      Numéro à utiliser : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
    if yes:
        raise SetupError("Aucun fichier OPTI_CLOUD.zip / « opti cloud.sql » trouvé : indiquez-le avec --source.")
    typed = input("      Chemin de OPTI_CLOUD.zip (ou de « opti cloud.sql ») : ").strip().strip('"')
    return resolve_source(typed, yes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Installation locale guidée d'Opti Cloud.")
    ap.add_argument("--source", help="OPTI_CLOUD.zip ou « opti cloud.sql » (sinon : recherche automatique, puis question).")
    ap.add_argument("--archive-dir", help=f"Dossier d'archive HORS du projet (défaut : {default_archive_dir()}).")
    ap.add_argument("--root-user", default="root", help="Compte administrateur MySQL (défaut : root).")
    ap.add_argument("--root-password", help="Mot de passe de ce compte (sinon : variable MYSQL_ROOT_PASSWORD, puis question ; vide sous WAMP).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, help="Port MySQL (sinon : essai de 3306, 3307 puis 3308).")
    ap.add_argument("--reset", action="store_true", help="Si la base Django contient déjà des données, les vider et réimporter.")
    ap.add_argument("--yes", action="store_true", help="Ne pose aucune question quand une valeur par défaut existe.")
    ap.add_argument("--run-tests", action="store_true", help="Lance aussi la suite de tests à la fin.")
    args = ap.parse_args(argv)

    print("=" * 78 + "\n  Opti Cloud : installation locale guidée\n" + "=" * 78)
    try:
        if sys.version_info < (3, 12):
            raise SetupError(f"Python 3.12 ou plus récent est requis (version actuelle : {sys.version.split()[0]}).")
        try:
            _mysql_driver()
        except ImportError as exc:
            raise SetupError("Le connecteur MySQL (PyMySQL) n'est pas installé. Lancez d'abord : pip install -r requirements.txt") from exc

        archive_dir = Path(args.archive_dir).expanduser().resolve() if args.archive_dir else default_archive_dir()
        check_archive_dir(archive_dir)                      # contrôlé AVANT de toucher à MySQL ou au .env

        # 1 -- fichiers d'origine
        step(1, "Recherche de vos fichiers d'origine")
        source = resolve_source(args.source, args.yes)
        ok(f"source : {source}")
        tmp = Path(tempfile.mkdtemp(prefix="opticloud_setup_"))
        try:
            if source.suffix.lower() == ".zip":
                zip_path, sql_path = source, extract_sql_from_zip(source, tmp)
                ok(f"dump trouvé dans le ZIP ({find_sql_in_zip(source)})")
            else:
                zip_path, sql_path = None, source
            sql_sha = sha256_file(sql_path)
            info(f"empreinte SHA-256 du dump : {sql_sha}")

            # 2 -- connexion administrateur
            step(2, "Connexion à MySQL")
            password = args.root_password
            if password is None:
                password = os.environ.get("MYSQL_ROOT_PASSWORD")
            if password is None:
                password = "" if args.yes else getpass.getpass(f"      Mot de passe MySQL de « {args.root_user} » (Entrée si vide, cas habituel de WAMP) : ")
            admin, port = connect_admin(args.host, args.port, args.root_user, password)
            cur = admin.cursor()
            cur.execute("SELECT VERSION()")
            ok(f"connecté, serveur {cur.fetchone()[0]} sur le port {port}")

            # 3 -- bases et comptes
            step(3, "Création des bases et des comptes dédiés")
            env_path = BASE / ".env"
            secret_key, rw_password, ro_password, reused = choose_secrets(parse_env(env_path.read_text(encoding="utf-8")) if env_path.exists() else {})
            setup_database_and_users(admin, rw_password, ro_password)
            if reused:
                info("mots de passe existants conservés (le .env déjà configuré reste valable)")
            ok(f"bases « {DJANGO_DB} » et « {LEGACY_DB} » prêtes (utf8mb4)")
            ok(f"comptes « {APP_USER} » (écriture sur {DJANGO_DB} seulement) et « {RO_USER} » (lecture seule sur {LEGACY_DB})")
            ok(check_php_database_is_out_of_reach(args.host, port, rw_password, ro_password, admin))

            # 4 -- .env
            step(4, "Écriture du fichier .env")
            if env_path.exists():
                backup = BASE / f".env.bak-{datetime.datetime.now():%Y%m%d_%H%M%S}"
                shutil.copy2(env_path, backup)
                info(f"ancien .env sauvegardé : {backup.name}")
            env_path.write_text(render_env(secret_key=secret_key, db_port=port, rw_password=rw_password,
                                           ro_password=ro_password, archive_dir=archive_dir), encoding="utf-8", newline="\n")
            ok(f".env écrit ({env_path})")

            # 5 -- archive des originaux
            step(5, "Archivage de vos originaux hors du projet (lecture seule, SHA-256)")
            snap = existing_snapshot_for(archive_dir, sql_sha)
            if snap:
                ok(f"déjà archivé : {snap}")
            else:
                cmd = ["backup_dump", "--dump", str(sql_path)] + (["--zip", str(zip_path)] if zip_path else [])
                manage(*cmd)
            manage("backup_dump", "--verify")
            ok(f"archive dans {archive_dir}")

            # 6 -- copie de travail du dump
            step(6, "Chargement du dump dans la copie de travail (utf-8)")
            loaded = load_dump_into_legacy(args.host, port, args.root_user, password, sql_path)
            ok(f"{sum(loaded.values())} lignes chargées dans {len(loaded)} tables")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # 7 -- schéma + import vérifié
        step(7, "Création du schéma Django puis import vérifié de vos données")
        manage("migrate", "--verbosity", "0")
        already = django_target_row_count(args.host, port, APP_USER, rw_password)
        if already and not args.reset:
            ok(f"la base Django contient déjà {already} lignes : import non refait (utilisez --reset pour réimporter)")
        else:
            cmd = ["import_legacy"] + (["--reset", "--confirm-database", DJANGO_DB] if already else [])
            manage(*cmd)
        manage("check")
        if args.run_tests:
            manage("test")

        print("\n" + "=" * 78)
        print("  Installation terminée.\n")
        print("  Lancez le site :   python manage.py runserver")
        print("  puis ouvrez :      http://127.0.0.1:8000/")
        print("  (ou double-cliquez sur LANCER_OPTI_CLOUD.bat)")
        print("=" * 78)
        return 0
    except SetupError as exc:
        print(f"\n  ERREUR : {exc}\n  Rien n'a été modifié dans vos fichiers d'origine ni dans votre base PHP.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n  Interrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
