from django.db import connections
from django.test import SimpleTestCase, TransactionTestCase

from apps.core.legacy import safety

DEFAULT = {"NAME": "opti_cloud", "ENGINE": "django.db.backends.mysql", "HOST": "127.0.0.1"}
LEGACY = {"NAME": "opti_cloud_legacy", "ENGINE": "django.db.backends.mysql", "HOST": "127.0.0.1"}
PROTECTED = ["opti cloud"]


def cfg(base, **kw):
    return {**base, **kw}


class SafeConfigTests(SimpleTestCase):
    def test_nominal_configuration_is_accepted(self):
        safety.assert_safe_config(DEFAULT, LEGACY, PROTECTED)

    def test_php_original_database_is_refused_as_target(self):
        for name in ("opti cloud", "OPTI CLOUD", "Opti Cloud"):
            with self.subTest(name):
                with self.assertRaisesMessage(safety.SafetyError, "PROTÉGÉE"):
                    safety.assert_safe_config(cfg(DEFAULT, NAME=name), LEGACY, PROTECTED)

    def test_legacy_database_is_refused_as_target(self):
        with self.assertRaisesMessage(safety.SafetyError, "identique à LEGACY_DB_NAME"):
            safety.assert_safe_config(cfg(DEFAULT, NAME="opti_cloud_legacy"), LEGACY, PROTECTED)
        with self.assertRaisesMessage(safety.SafetyError, "identique à LEGACY_DB_NAME"):
            safety.assert_safe_config(cfg(DEFAULT, NAME="OPTI_CLOUD_LEGACY"), LEGACY, PROTECTED)

    def test_system_databases_are_refused(self):
        for name in ("mysql", "sys", "information_schema", "performance_schema", "phpmyadmin", "test"):
            with self.subTest(name):
                with self.assertRaises(safety.SafetyError):
                    safety.assert_safe_config(cfg(DEFAULT, NAME=name), LEGACY, PROTECTED)

    def test_extra_protected_names_from_the_env_are_honoured(self):
        with self.assertRaises(safety.SafetyError):
            safety.assert_safe_config(cfg(DEFAULT, NAME="ma_base_php"), LEGACY, PROTECTED + ["Ma_Base_PHP"])

    def test_empty_target_name_is_refused(self):
        with self.assertRaises(safety.SafetyError):
            safety.assert_safe_config(cfg(DEFAULT, NAME=""), LEGACY, PROTECTED)

    def test_non_local_server_is_refused(self):
        with self.assertRaisesMessage(safety.SafetyError, "pas local"):
            safety.assert_safe_config(cfg(DEFAULT, HOST="192.168.1.20"), LEGACY, PROTECTED)
        with self.assertRaisesMessage(safety.SafetyError, "pas local"):
            safety.assert_safe_config(DEFAULT, cfg(LEGACY, HOST="db.example.com"), PROTECTED)

    def test_sqlite_is_refused(self):
        with self.assertRaisesMessage(safety.SafetyError, "MySQL"):
            safety.assert_safe_config(cfg(DEFAULT, ENGINE="django.db.backends.sqlite3"), LEGACY, PROTECTED)


class ResetTests(SimpleTestCase):
    def test_reset_requires_the_confirmation(self):
        with self.assertRaisesMessage(safety.SafetyError, "--confirm-database"):
            safety.assert_reset_allowed(DEFAULT, LEGACY, None, PROTECTED)

    def test_reset_with_wrong_or_differently_cased_confirmation_is_refused(self):
        for typed in ("opti_cloud_legacy", "opti cloud", "OPTI_CLOUD", "opti_cloud "):
            with self.subTest(typed):
                with self.assertRaisesMessage(safety.SafetyError, "ne correspond pas"):
                    safety.assert_reset_allowed(DEFAULT, LEGACY, typed, PROTECTED)

    def test_reset_with_exact_confirmation_is_accepted(self):
        safety.assert_reset_allowed(DEFAULT, LEGACY, "opti_cloud", PROTECTED)

    def test_reset_is_refused_on_protected_database_even_with_the_right_confirmation(self):
        for name in ("opti cloud", "opti_cloud_legacy"):
            with self.subTest(name):
                with self.assertRaises(safety.SafetyError):
                    safety.assert_reset_allowed(cfg(DEFAULT, NAME=name), LEGACY, name, PROTECTED)


class TargetSignatureTests(TransactionTestCase):
    databases = {"default", "legacy"}

    def test_django_database_is_recognised(self):
        self.assertTrue(safety.target_is_django_db(connections["default"]))

    def test_legacy_copy_is_never_taken_for_the_django_database(self):
        self.assertFalse(safety.target_is_django_db(connections["legacy"]))
