"""Migre les 9 tables du dump d'origine vers la base Django, avec vérification exacte et rapport."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.legacy import archive, report, safety
from apps.core.legacy.importer import MigrationFailure, run_import


class Command(BaseCommand):
    help = (
        "Copie les 9 tables de la copie de travail (opti_cloud_legacy) vers la base Django, après avoir vérifié l'archive d'origine "
        "(SHA-256) et comparé fichier SQL ↔ legacy ↔ Django valeur par valeur. Transactionnel : au moindre écart, tout est annulé. "
        "Aucune correction automatique des données."
    )

    def add_arguments(self, parser):
        parser.add_argument("--archive-dir", help="Dossier d'archive hors projet (défaut : ARCHIVE_DIR).")
        parser.add_argument("--snapshot", help="Snapshot à utiliser (défaut : le plus récent).")
        parser.add_argument("--dry-run", action="store_true", help="Simule tout puis annule : la base Django n'est pas modifiée.")
        parser.add_argument("--reset", action="store_true",
                            help="Vide les 9 tables de la base Django avant l'import (dans la même transaction). Exige --confirm-database.")
        parser.add_argument("--confirm-database", help="Nom EXACT de la base cible, obligatoire avec --reset.")
        parser.add_argument("--report-dir", help="Dossier des rapports (défaut : docs/).")

    def handle(self, *args, **o):
        if o["confirm_database"] and not o["reset"]:
            raise CommandError("--confirm-database n'a de sens qu'avec --reset.")
        report_dir = Path(o["report_dir"]) if o["report_dir"] else Path(settings.BASE_DIR) / "docs"
        self.stdout.write(self.style.MIGRATE_HEADING("Migration Opti Cloud : " + ("SIMULATION" if o["dry_run"] else "IMPORT RÉEL")))
        try:
            result = run_import(archive_dir=o["archive_dir"], snapshot=o["snapshot"], dry_run=o["dry_run"], reset=o["reset"],
                                confirm_database=o["confirm_database"], log=self.stdout.write)
        except (safety.SafetyError, archive.ArchiveError) as exc:
            raise CommandError(f"REFUSÉ : {exc}") from exc
        except MigrationFailure as exc:
            files = report.write_reports(exc.result, report_dir, failed=True)
            self.stderr.write(self.style.ERROR(f"ÉCHEC : {exc}"))
            raise CommandError(f"Migration en échec (aucune donnée conservée). Rapport : {files[0]}") from exc
        files = report.write_reports(result, report_dir)
        self.stdout.write(self.style.SUCCESS(f"Verdict : {result['verdict']} — rapport : {files[0]}"))
