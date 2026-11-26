"""Archive le ZIP et le dump d'origine HORS du projet : copie, lecture seule, empreintes SHA-256."""
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.legacy import archive


class Command(BaseCommand):
    help = (
        "Archive le dump SQL (et le ZIP) d'origine dans un dossier HORS du projet : copie vérifiée, fichiers en lecture seule, "
        "manifeste SHA-256. Les fichiers d'origine ne sont jamais modifiés. Avec --verify : contrôle seulement les empreintes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dump", help="Chemin du dump SQL d'origine (ex. « opti cloud.sql »).")
        parser.add_argument("--zip", help="Chemin du ZIP d'origine (OPTI_CLOUD.zip), facultatif.")
        parser.add_argument("--archive-dir", help="Dossier d'archive HORS projet (défaut : ARCHIVE_DIR du .env).")
        parser.add_argument("--verify", action="store_true", help="Vérifie les empreintes d'un snapshot existant sans rien copier.")
        parser.add_argument("--snapshot", help="Nom du snapshot à vérifier (défaut : le plus récent).")

    def handle(self, *args, **o):
        try:
            adir = archive.resolve_archive_dir(o["archive_dir"])
            if o["verify"]:
                return self._verify(adir, o["snapshot"])
            return self._backup(adir, o)
        except archive.ArchiveError as exc:
            raise CommandError(str(exc)) from exc

    def _verify(self, adir: Path, name):
        snap = archive.resolve_snapshot(adir, name)
        results = archive.verify_snapshot(snap)
        self.stdout.write(f"Snapshot : {snap}")
        for r in results:
            self.stdout.write(f"  [{'OK' if r['ok'] else 'ÉCHEC'}] {r['name']}  SHA-256 {r['expected'][:16]}…")
        if not all(r["ok"] for r in results):
            raise CommandError("Au moins un fichier archivé ne correspond plus à son empreinte : ne l'utilisez pas.")
        self.stdout.write(self.style.SUCCESS("Archive intacte."))

    def _backup(self, adir: Path, o):
        if not o["dump"]:
            raise CommandError("Indiquez le dump d'origine avec --dump (ou utilisez --verify).")
        sources = [Path(o["dump"]).expanduser().resolve()]
        if o["zip"]:
            sources.append(Path(o["zip"]).expanduser().resolve())
        for s in sources:
            if not s.is_file():
                raise CommandError(f"Fichier introuvable : {s}")
            if adir == s.parent or adir in s.parents:
                raise CommandError(f"{s} se trouve déjà dans le dossier d'archive : indiquez le fichier d'origine.")
        if sources[0].suffix.lower() != ".sql":
            raise CommandError("--dump doit être un fichier .sql")
        if len({s.name for s in sources}) != len(sources):
            raise CommandError("Le dump et le ZIP ne peuvent pas avoir le même nom.")

        before = {s: archive.sha256_file(s) for s in sources}
        adir.mkdir(parents=True, exist_ok=True)
        snap = adir / archive.snapshot_name()
        try:
            snap.mkdir()                      # jamais d'écrasement : échoue si le snapshot existe déjà
        except FileExistsError as exc:
            raise CommandError(f"Le snapshot {snap.name} existe déjà : rien n'est écrasé. Réessayez dans une seconde.") from exc

        entries = []
        for s in sources:
            dest = snap / s.name
            shutil.copyfile(s, dest)
            h = archive.sha256_file(dest)
            if h != before[s]:
                raise CommandError(f"Copie corrompue pour {s.name} (empreinte différente) : snapshot incomplet {snap}")
            archive.make_readonly(dest)
            entries.append((h, s.name))
            self.stdout.write(f"  copié : {s.name}  SHA-256 {h}")
        archive.write_manifest(snap, entries)

        for s in sources:                      # contrôle APRÈS : l'original n'a pas bougé
            if archive.sha256_file(s) != before[s]:
                raise CommandError(f"ALERTE : le fichier d'origine {s} a changé pendant la sauvegarde.")
        self.stdout.write(self.style.SUCCESS(f"Snapshot créé : {snap}"))
        self.stdout.write(f"  Originaux intacts, copies en lecture seule, manifeste : {snap / archive.MANIFEST_NAME}")
