# Opti Cloud : version Django (jalons J1 à J4 : socle, migration des données, tableau de bord et les six modules)

Reconstruction de l'application PHP **Opti Cloud** avec **Python + Django 5.2 + MySQL**.
* **J1** : configuration, les 9 modèles, les migrations, l'archivage des originaux et la **migration vérifiée des données**.
* **J2** : le **tableau de bord** et le **module Catégories** complet (liste, ajout, modification, suppression, impression PDF).
* **J3** : les modules **Marques** et **Fournisseurs**, complets, bâtis sur la même base.
* **J4** : les modules **Verres**, **Lentilles** et **Montures**, complets (ID en lecture seule à la modification, listes déroulantes pour les ENUM d'origine).
  Les six modules de l'application d'origine sont donc reconstruits.

## Démarrage rapide (Windows + WAMP)

1. Installez **Python 3.12 ou plus récent** (python.org) en cochant **Add python.exe to PATH**.
2. Démarrez **WAMP** : l'icône doit être **verte**.
3. **Double-cliquez sur `INSTALLER_ET_LANCER.bat`**.

Il fait tout, une seule fois : environnement Python et dépendances, repérage du port MySQL, création des bases `opti_cloud` et `opti_cloud_legacy`,
création de deux comptes dédiés aux mots de passe aléatoires, écriture du `.env`, archivage de vos originaux hors du projet, import de vos données avec
vérification complète, puis ouverture du site sur **http://127.0.0.1:8000/**.
Il demande simplement le mot de passe MySQL de `root` (**laissez vide sous WAMP**, c'est le réglage par défaut) et, s'il ne les trouve pas seul,
l'emplacement de `OPTI_CLOUD.zip`. Si votre application PHP a été utilisée depuis l'export du dump, donnez-lui plutôt un **nouvel export** `opti cloud.sql`
(phpMyAdmin, base `opti cloud`, Exporter, format SQL, jeu de caractères utf-8).

Les fois suivantes : **double-cliquez sur `LANCER_OPTI_CLOUD.bat`**. Rien n'est modifié dans vos fichiers d'origine ni dans votre base PHP `opti cloud`.
En ligne de commande : `python setup_local.py` (options : `--source`, `--archive-dir`, `--root-password`, `--port`, `--reset`, `--run-tests`).

**Publier sur GitHub** : voir `docs/GITHUB.md` (dépôt privé conseillé ; vos données, vos mots de passe et le `.env` ne sont jamais versionnés ; les tests tournent automatiquement sur MySQL à chaque envoi).

**Héberger sur Vercel** : voir `docs/VERCEL.md` (le projet utilise `PyMySQL` pur Python, `WhiteNoise` et `vercel.json` afin de compiler et tourner sur Vercel Functions sans bibliothèque système C).

Les sections suivantes décrivent la même installation **à la main**, si vous préférez ou en cas de problème.

## Principes de sécurité des données

* **Les originaux (`OPTI_CLOUD.zip` et `opti cloud.sql`) restent HORS du projet**, en lecture seule, avec empreintes SHA-256 (`backup_dump`). Aucune commande ne les modifie ; leurs empreintes sont revérifiées avant et après chaque import.
* **La base PHP d'origine n'est jamais touchée** : Django ne s'y connecte pas, et son compte MySQL n'a aucun droit dessus.
* `opti_cloud_legacy` est une copie de travail jetable du dump, lue par un compte **en lecture seule** (`opticloud_ro`).
* `opti_cloud` est la seule base où Django écrit.
* **Aucune donnée n'est corrigée** : les valeurs sont copiées telles quelles, le texte déjà corrompu est seulement signalé dans le rapport.

## Arborescence

```
opti_cloud/
├── manage.py
├── requirements.txt / requirements-dev.txt
├── .env.example                      # modèle de configuration (le vrai .env n'est jamais versionné)
├── config/                           # settings.py (MySQL, .env), urls.py, wsgi.py, asgi.py
├── apps/
│   ├── core/                         # sécurité et migration
│   │   ├── legacy/                   # dumpparser, rowsets, archive, safety, model_parity, schema_diff, anomalies, importer, report
│   │   ├── management/commands/      # backup_dump.py, import_legacy.py
│   │   ├── routers.py                # interdit toute migration/écriture Django sur la base legacy
│   │   ├── forms.py views.py pdf.py  # base commune des modules : formulaires, vues CRUD, générateur de PDF
│   │   ├── fonts/                    # Liberation Sans (équivalent d'Arial, licence SIL OFL) pour les PDF
│   │   └── tests/                    # tests de migration (fixtures/mini_dump.sql : données fictives), de PDF et batterie commune des modules
│   ├── dashboard/                    # tableau de bord (J2)
│   ├── categories/ marques/ fournisseurs/ verres/ lentilles/ montures/   # les six modules : forms, views, urls, pdf, tests
│   ├── clients/                      # modèle seulement (aucun écran, table vide)
│   └── patients/                     # Patient + Ordonnance (aucun écran, données conservées)
├── docs/
│   ├── migration_report.md / .json   # rapport de migration (généré)
│   ├── schema_differences.md         # écarts de schéma PHP ↔ Django
│   └── relations.md                  # relations logiques entre les tables
├── templates/                        # base_root, base_module, layouts/ (liste, formulaire, confirmation), dashboard/, categories/
└── static/                           # css/dashboard.css, css/module.css (repris des pages PHP), js/app.js
```

## Installation sous Windows avec WAMP

### 1. Démarrer WAMP et identifier le serveur
1. Lancez **WampServer64** ; l'icône doit être **verte** (sinon : clic gauche, *Démarrer tous les services*).
2. Ouvrez `http://localhost/phpmyadmin` (utilisateur `root`, mot de passe vide).
3. Onglet **SQL**, exécutez `SELECT VERSION(), @@port;` : notez le **port** pour `DB_PORT`.

### 2. Créer les bases et les comptes (onglet SQL de phpMyAdmin, en `root`)
Remplacez les deux mots de passe.

```sql
CREATE DATABASE opti_cloud        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE opti_cloud_legacy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'opticloud'@'localhost'    IDENTIFIED BY 'MotDePasseRW';
CREATE USER 'opticloud'@'127.0.0.1'    IDENTIFIED BY 'MotDePasseRW';
GRANT ALL PRIVILEGES ON `opti\_cloud`.*             TO 'opticloud'@'localhost', 'opticloud'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `test\_opti\_cloud`.*        TO 'opticloud'@'localhost', 'opticloud'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `test\_opti\_cloud\_legacy`.* TO 'opticloud'@'localhost', 'opticloud'@'127.0.0.1';

CREATE USER 'opticloud_ro'@'localhost' IDENTIFIED BY 'MotDePasseRO';
CREATE USER 'opticloud_ro'@'127.0.0.1' IDENTIFIED BY 'MotDePasseRO';
GRANT SELECT ON `opti\_cloud\_legacy`.* TO 'opticloud_ro'@'localhost', 'opticloud_ro'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Le compte `opticloud` n'a **aucun droit** sur `opti_cloud_legacy` ni sur la base PHP `opti cloud` ; `opticloud_ro` n'a que `SELECT`.
**Important : les `\_` sont indispensables.** Dans un `GRANT`, `_` est un joker : `opti_cloud` non échappé couvrirait aussi la base PHP `opti cloud` (avec une espace).

### 3. Environnement Python
```powershell
cd C:\Projets\opti_cloud
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # si refus : Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env
notepad .env                          # renseigner mots de passe, port, SECRET_KEY, ARCHIVE_DIR
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```
Gardez la `SECRET_KEY` entre guillemets simples. `ARCHIVE_DIR` doit désigner un dossier **hors du projet** (utilisez des `/`, par exemple `C:/OptiCloud_Archives`).

### 4. Archiver les originaux (étape à faire en premier)
```powershell
python manage.py backup_dump --dump "C:\chemin\vers\opti cloud.sql" --zip "C:\chemin\vers\OPTI_CLOUD.zip"
```
Cela crée `snapshot_AAAAMMJJ_HHMMSS` dans `ARCHIVE_DIR` : copies en lecture seule + `MANIFEST.sha256`. Vos fichiers d'origine ne sont pas modifiés.
Contrôle à tout moment : `python manage.py backup_dump --verify`.

### 5. Charger le dump dans la copie de travail (une seule fois)
Dans phpMyAdmin : cliquez sur la base **`opti_cloud_legacy`** (jamais `opti_cloud`) → **Importer** → choisissez `opti cloud.sql` →
**Jeu de caractères du fichier : utf-8** → **Exécuter**. Vous devez voir 9 tables.

### 6. Créer le schéma, simuler, puis importer
```powershell
python manage.py migrate
python manage.py import_legacy --dry-run      # simulation : ne modifie rien, écrit docs/migration_report_dry_run.md
python manage.py import_legacy                # import réel : écrit docs/migration_report.md
```

Le résultat attendu avec vos données actuelles est **Verdict : OK, 70 lignes** (marque 29, monture 9, categorie 8, fournisseur 6, ordonnance 6, patient 5, lentille 4, verre 3, client 0).

### 7. Voir le site
```powershell
python manage.py runserver
```
Ouvrez ensuite **http://127.0.0.1:8000/** : c'est le tableau de bord. WAMP doit rester vert (il fournit MySQL ; Django sert lui-même les pages sur le port 8000).
Il faut une connexion Internet : comme l'application d'origine, les pages chargent Bootstrap 5.3.2, Bootstrap Icons et Font Awesome depuis leur CDN.

| Adresse | Page |
|---|---|
| `/` | Tableau de bord (5 compteurs lus en base) |
| `/categories/` | Liste des catégories, avec Ajouter et Imprimer |
| `/categories/` `/marques/` `/fournisseurs/` `/verres/` `/lentilles/` `/montures/` | Listes, avec Ajouter et Imprimer |
| `/<module>/ajouter/` · `/<module>/<id>/modifier/` · `/<module>/<id>/supprimer/` | Formulaires et confirmation |
| `/<module>/imprimer/` | PDF affiché dans le navigateur |

Chaque page de module a un bouton discret **« Retour au tableau de bord »**. Le champ « Recherche rapide » du tableau de bord reste décoratif, comme dans l'original (la recherche est prévue en phase 2).

### 8. Tests
```powershell
python manage.py test                         # toute la suite, sur MySQL, avec des données fictives
python manage.py test apps.montures           # un module (categories, marques, fournisseurs, verres, lentilles, montures)
```
Les contrôles de marges et de couleur des PDF mesurent le rendu image avec `pdftoppm` (poppler) : s'il n'est pas installé (cas habituel sous Windows), ces trois contrôles sont ignorés ; les autres vérifications du PDF (texte, pagination, orientation, en-tête répété) s'exécutent toujours.

## Commandes

| Commande | Rôle |
|---|---|
| `backup_dump --dump … [--zip …]` | Archive les originaux hors du projet (lecture seule, SHA-256). Ne les modifie jamais, n'écrase jamais un snapshot. |
| `backup_dump --verify [--snapshot NOM]` | Revérifie les empreintes de l'archive. |
| `import_legacy --dry-run` | Exécute tout, vérifie tout, puis annule : la base Django (lignes et compteurs) reste intacte. |
| `import_legacy` | Importe les 9 tables si la base Django est vide, dans **une transaction**. |
| `import_legacy --reset --confirm-database opti_cloud` | Vide puis réimporte, dans la même transaction (un échec restaure l'état précédent). |

Ce que `import_legacy` contrôle **à chaque exécution** : bases protégées respectées, serveur local, archive intacte (SHA-256), 9 tables ↔ 9 modèles, aucune colonne oubliée,
caractères représentables en latin1, copie legacy = fichier SQL (valeur par valeur), base cible bien Django, puis comptages, clés, valeurs et empreintes identiques sur
**4 sources** (fichier SQL, legacy, Django en SQL, Django en ORM), compteurs auto-incrément, schémas, archive intacte après exécution.

`--reset` refuse : l'absence de `--confirm-database`, un nom différent de la base cible, la base PHP d'origine (`opti cloud`), la copie `opti_cloud_legacy`, les bases système,
toute base listée dans `PROTECTED_DATABASES`, un serveur non local, et une base qui n'est pas une base Django (pas de `django_migrations`).

## Dépannage

| Message | Cause probable |
|---|---|
| `Can't connect to MySQL server ... (10061)` | WAMP pas vert, ou mauvais `DB_PORT` |
| `Access denied for user` | mot de passe du `.env` différent de celui du §2, ou compte `127.0.0.1` manquant |
| `Copie legacy identique au fichier SQL` en échec | dump chargé avec un mauvais jeu de caractères : vider `opti_cloud_legacy` et réimporter en **utf-8** |
| `REFUSÉ : … PROTÉGÉE` | `DB_NAME` désigne une base protégée : corrigez le `.env` |
| `La base cible est vide` en échec | l'import a déjà été fait ; pour recommencer : `--reset --confirm-database opti_cloud` |
| `Empreinte SHA-256 différente du manifeste` | un fichier archivé a été altéré : restaurez-le depuis votre copie de sauvegarde |

## Choix de reproduction (les six modules)

* **Design repris à l'identique** : le CSS est extrait des pages PHP d'origine (`dashboard.css`, `module.css`) ; mêmes icônes, couleurs, bandeaux, cartes et tableaux. Seuls ajouts : le bouton « Retour au tableau de bord » et un contour de focus visible au clavier.
* **Règles d'ID d'origine** : à l'ajout, l'ID est saisi à la main ; à la modification, l'ID reste modifiable (Catégories). Un ID déjà utilisé affiche maintenant un message au lieu d'échouer en silence ; un ajout ne peut jamais écraser une ligne existante.
* **Suppression** : fenêtre de confirmation JavaScript, puis page de confirmation, puis suppression par formulaire sécurisé (POST + jeton CSRF). Un simple lien ne supprime rien.
* **Textes corrigés** : « Liste des Services » (copié d'un autre projet) devient « Liste des catégories » ; « supprimer ce service » devient « supprimer cette catégorie » ; accents ajoutés (« catégorie »). Le lien « Retour » du formulaire de modification, cassé dans l'original, est réparé.
* **Champs obligatoires** : comme dans les formulaires PHP, tous les champs sont obligatoires à l'ajout et à la modification (même si la base accepte les valeurs vides).
* **Marques** : le champ « Pays » du formulaire de modification utilisait une classe CSS inexistante (`pays-control`) et s'affichait sans style ; il a maintenant le style des autres champs. Libellés « pays » et « description » mis en majuscule initiale, « Liste des marque » devenu « Liste des marques ».
* **Fournisseurs** : « Fornisseur » corrigé en « Fournisseur » partout ; « ce service » devient « ce fournisseur ». Le champ Email reste un champ texte mais son format est maintenant contrôlé. L'ID, auto-incrémenté en base, est saisi à la main comme dans l'original ; **0 est refusé** (MySQL le remplacerait en silence par le numéro suivant) ; la numérotation automatique reprend après le plus grand ID saisi.
* **Verres, Lentilles, Montures** : l'ID (Code Verre, ID Lentille, ID Monture) est saisi à l'ajout et **en lecture seule** à la modification, comme dans l'original ; il ne peut pas être changé même par une requête forgée. L'ID d'une monture, auto-incrémenté en base, est saisi à la main ; 0 est refusé.
* **Listes déroulantes** : le genre des montures, le type et la correction des lentilles sont des listes déroulantes qui n'offrent que les valeurs valides de l'ENUM d'origine (accents compris), alors que l'original avait un champ texte libre (une valeur invalide y était enregistrée vide).
* **Bogue d'origine corrigé (lentilles)** : le formulaire de modification n'envoyait pas « ID fournisseur » alors que le script de mise à jour l'écrivait : **chaque modification remettait le fournisseur de la lentille à 0**. Le champ est maintenant présent à la modification (pré-rempli).
* **Prix et nombres** : une virgule ou un point sont acceptés (« 350,50 »), la notation scientifique (« 1e3 ») est refusée, les prix et stocks ne peuvent pas être négatifs, et le nombre de décimales respecte la précision de la base. Les montants s'affichent avec un point (« 350.00 DH »), comme dans l'original.
* **Relations** : Montures (marque, fournisseur, catégorie), Verres (fournisseur) et Lentilles (marque, fournisseur) gardent des champs texte libres, sans clé étrangère (décision validée) : les valeurs d'origine (« CH », « CAT07 », « ES ») ne correspondent à aucune ligne des autres tables et restent acceptées telles quelles. Des listes de choix pourront être ajoutées en phase 2, après nettoyage des données.
* **Verres** : le formulaire n'a pas d'icônes (comme l'original) ; la description est une zone de texte à l'ajout comme à la modification, pour ne jamais écraser les retours à la ligne.
* **PDF des montures et lentilles** : les colonnes « Cat. » (montures) et « Fourn. » (lentilles) étaient coupées ou invisibles dans l'original ; elles sont maintenant toutes visibles.
* **Valeurs vides** : une valeur absente en base s'affiche vide, jamais « None ».
* **PDF** : mêmes colonnes, titres, couleurs, orientation et marges (10 mm) que l'original ; retour à la ligne automatique, en-tête répété sur chaque page, aucune colonne coupée. Pour les fournisseurs, les largeurs sont redistribuées (colonne ID réduite, colonne Email élargie) afin que les adresses e-mail tiennent sur une ligne. Police Liberation Sans intégrée : les caractères hors alphabet latin (arabe, par exemple) ne s'impriment pas correctement dans les PDF.

Ne changez pas le fuseau horaire de Windows/WAMP entre le chargement du dump et l'import (colonnes `TIMESTAMP`) ; la comparaison fichier ↔ base le détecterait.
