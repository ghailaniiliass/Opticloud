class LegacyRouter:
    """Empêche toute migration ou écriture Django sur l'alias `legacy` (copie du dump d'origine)."""

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "legacy":
            return False
        return None
