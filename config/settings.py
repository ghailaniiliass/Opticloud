"""
Configuration d'Opti Cloud (Django 5.2 + MySQL).

Aucun secret n'est écrit ici : tout vient du fichier .env en local (voir .env.example)
ou des variables d'environnement en production (Vercel).
En local, si le .env est absent ou incomplet, Django s'arrête avec un message d'erreur explicite.
Sur Vercel, pendant `vercel build` (`collectstatic`) ou tant que la base MySQL cloud n'est pas
encore renseignée, un repli temporaire en `/tmp` permet au build et à l'aperçu de démarrer proprement.
"""
import os
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

# Vrai quand on lance `manage.py test` (les bases de test sont créées avec le compte lecture/écriture).
TESTING = "test" in sys.argv
IS_VERCEL = os.environ.get("VERCEL") == "1"

SECRET_KEY = env(
    "SECRET_KEY",
    default="vercel-preview-fallback-secret-key-configure-in-vercel-env" if IS_VERCEL else environ.NoValue,
)
DEBUG = env("DEBUG")

_DEFAULT_HOSTS = ["127.0.0.1", "localhost"]
if IS_VERCEL:
    _DEFAULT_HOSTS.append(".vercel.app")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=_DEFAULT_HOSTS)
if IS_VERCEL and ".vercel.app" not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://*.vercel.app"] if IS_VERCEL else [],
)
if IS_VERCEL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------
# Applications : un module = une application Django.
# Pas d'authentification pour l'instant (décision validée) : ni auth, ni sessions.
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.dashboard",
    "apps.categories",
    "apps.clients",
    "apps.fournisseurs",
    "apps.marques",
    "apps.montures",
    "apps.verres",
    "apps.lentilles",
    "apps.patients",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.VercelDemoDatabaseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Base de données : MySQL (WAMP en local, ou MySQL cloud sur Vercel).
# --------------------------------------------------------------------------
_HOST = env("DB_HOST", default="127.0.0.1")   # 127.0.0.1 force une connexion TCP vers le port indiqué
_PORT = env("DB_PORT", default="3306")
_TEST_OPTS = {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"}
_MYSQL_OPTIONS: dict = {
    "charset": "utf8mb4",
    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
}
if env.bool("DB_SSL", default=False):
    _MYSQL_OPTIONS["ssl"] = {}

if os.environ.get("DATABASE_URL"):
    _default_db = env.db("DATABASE_URL")
    if "mysql" in _default_db.get("ENGINE", ""):
        _default_db.setdefault("OPTIONS", {}).update(_MYSQL_OPTIONS)
        _default_db["TEST"] = dict(_TEST_OPTS)
elif IS_VERCEL and not os.environ.get("DB_NAME"):
    # Permet à `vercel build` (collectstatic) et au premier aperçu Vercel de fonctionner
    # tant que DB_HOST / DB_NAME / DB_USER / DB_PASSWORD (ou DATABASE_URL) ne sont pas définis.
    _default_db = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/opti_cloud_demo.sqlite3",
    }
else:
    _default_db = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": _HOST,
        "PORT": _PORT,
        "OPTIONS": dict(_MYSQL_OPTIONS),
        "TEST": dict(_TEST_OPTS),
    }

DATABASES = {"default": _default_db}

# Copie de travail du dump d'origine (`import_legacy`, en local ou pendant les tests MySQL).
if (TESTING and os.environ.get("DB_USER")) or os.environ.get("LEGACY_DB_USER") or not IS_VERCEL:
    DATABASES["legacy"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("LEGACY_DB_NAME", default="opti_cloud_legacy"),
        "USER": env("DB_USER") if TESTING else env("LEGACY_DB_USER"),
        "PASSWORD": env("DB_PASSWORD") if TESTING else env("LEGACY_DB_PASSWORD"),
        "HOST": _HOST,
        "PORT": _PORT,
        "OPTIONS": {"charset": "utf8mb4"},
        # Les tests ne migrent jamais cet alias : sa copie de test ressemble à la vraie copie du dump (aucune table Django).
        "TEST": {**_TEST_OPTS, "MIGRATE": False},
    }

# Aucune migration, aucune écriture applicative sur l'alias `legacy`.
DATABASE_ROUTERS = ["apps.core.routers.LegacyRouter"]

# --------------------------------------------------------------------------
# Sécurité de la migration
# --------------------------------------------------------------------------
# Dossier d'archive des originaux (ZIP + dump) : DOIT être hors du projet.
ARCHIVE_DIR = env("ARCHIVE_DIR", default="")
# Bases que `import_legacy` refuse de toucher (base PHP d'origine, etc.). `opti cloud` = nom relevé dans connexion.php.
PROTECTED_DATABASES = [n.strip() for n in env.list("PROTECTED_DATABASES", default=["opti cloud"]) if n.strip()]
# Valeurs propres à VOTRE base que le rapport de migration doit signaler comme « ressemblant à des essais » (facultatif, jamais supprimées).
TEST_LIKE_VALUES = [n.strip() for n in env.list("TEST_LIKE_VALUES", default=[]) if n.strip()]

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Casablanca"
USE_I18N = True
USE_TZ = False                    # les horodatages du dump ne doivent jamais être décalés
USE_THOUSAND_SEPARATOR = False

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
WHITENOISE_USE_FINDERS = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
