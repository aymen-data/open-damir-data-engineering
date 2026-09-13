# Open DAMIR — pipeline Data Engineering

Projet pédagogique indépendant sur les **données publiques réelles de l’Assurance Maladie**. Il transforme les fichiers mensuels Open DAMIR en Parquet contrôlé, calcule des indicateurs avec DuckDB et compare Python/Polars/DuckDB.

**Commencer par [le rapport visuel](reports/rapport.html)** (ouvrir dans un navigateur), puis [les résultats exécutés](reports/RESULTATS.md).

## Ce qui est livré

- Janvier 2025 téléchargé intégralement depuis le catalogue officiel ; aucune donnée synthétique dans les résultats métier.
- Source gzip et CSV conservés, empreintes SHA-256, origine et date de récupération enregistrées.
- Lecture progressive Arrow par blocs de 8 Mio, nettoyage Polars, sortie Parquet Zstandard par mois.
- Codes conservés en texte ; 14 colonnes numériques en décimal exact (24 chiffres, dont 6 décimales).
- Contrôles bloquants avant publication ; diagnostics sur les valeurs particulières.
- Sept requêtes SQL : mois, régions, prestations, âge, période de soins, périmètre statistique et jointure avec les libellés officiels.
- Benchmark sur un million de lignes réelles, cinq méthodes, trois répétitions et contrôle d’équivalence exacte.
- Tests hors réseau, scripts PowerShell/Bash, script R complémentaire, documentation et dépôt Git local.

Le volume exact et les mesures figurent dans `reports/RESULTATS.md`. Le benchmark est un échantillon technique distinct des analyses, qui portent sur le fichier mensuel complet.

## Installation standard

Python 3.11 ou supérieur compatible avec les versions du projet ; validation effectuée avec Python 3.12 sous Windows. Prévoir environ **10 Go d’espace libre par mois** pour les différentes représentations, avec une marge pour les fichiers temporaires. La taille varie selon le mois.

Depuis ce dossier, dans PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m damir.cli run --months 202501
.\.venv\Scripts\python.exe -m pytest -q
```

Sous Linux/macOS :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PYTHON=.venv/bin/python bash scripts/run.sh 202501
.venv/bin/python -m pytest -q
```

Si l’installation de l’environnement de construction bloque : installer `setuptools` et `wheel`, puis relancer `pip install --no-build-isolation -e ".[dev]"`. Ne pas ignorer les erreurs de dépendances.

Les versions directes sont fixées dans `pyproject.toml`. `requirements-lock.txt` décrit l’environnement Python validé et ses dépendances transitives. Il ne garantit pas la disponibilité des mêmes roues sur toute architecture.

## Utilisation

La racine des données est le dossier courant, ou celle donnée avec `--root` **avant** la sous-commande.

```bash
python -m damir.cli fetch --months 202501
python -m damir.cli transform --months 202501
python -m damir.cli analyze
python -m damir.cli benchmark --rows 1000000 --repeats 3
python -m damir.cli report
python scripts/verify_source.py
```

La commande `run` exécute ces opérations. Pour ajouter février :

```bash
python -m damir.cli run --months 202501 202502
```

Janvier déjà validé est réutilisé. Les analyses portent sur **toutes les partitions publiées** dans cette racine, y compris celles de précédentes exécutions. Pour un périmètre isolé, utiliser une autre racine avec `--root`.

La source peut être révisée : `fetch --months 202501 --refresh` récupère la version actuellement publiée. `transform` reconstruit la partition si son empreinte a changé. Le téléchargement reprend depuis le début après un échec réseau ; il ne reprend pas à l’octet interrompu. Une conversion interrompue reprend au début du mois.

## Structure

```text
src/damir/         CLI, téléchargement, transformation, qualité, benchmark, rapport
src/damir/sql/     requêtes SQL lisibles et modifiables
tests/             tests unitaires et intégration sur mini-données fictives explicites
scripts/           lanceurs Windows/Bash, analyse R et archive légère
references/        dictionnaire officiel et nomenclatures extraites
data/raw/          fichiers officiels ; exclus de Git
data/curated/      month=AAAAMM/part-000.parquet ; exclus de Git
data/manifests/    empreintes, nombre de lignes, tailles et versions
data/benchmark/    mêmes lignes dans deux formats ; exclus de Git
reports/           résultats, contrôles qualité, benchmark, rapport autonome
docs/              explications, choix métier, limites et validation
logs/              journal d’exécution ; exclu de Git
```

## Interprétation des données

Une ligne est un agrégat de remboursements selon plusieurs dimensions. **Pas d’identifiant de patient ni d’établissement individuel exploitable ici.** Les codes de catégories d’établissement ne sont pas des identifiants FINESS.

Les analyses principales utilisent `FLT_REM_MNT` (part légale), `FLT_PAI_MNT` (dépense préfiltrée) et `FLT_ACT_QTE` (quantité préfiltrée). Les colonnes brutes restent disponibles, mais certains usages nécessitent des filtres sur `PRS_REM_TYP` pour éviter les doubles comptes. Voir [les choix métier](docs/DONNEES.md).

Les sommes ne constituent pas une estimation de toutes les dépenses de santé françaises. Les tranches d’âge ne sont pas des âges individuels. Les régions suivent la nomenclature spécifique de la source, incluant des regroupements et des valeurs inconnues.

## Limites de cette première version

- Données testées : janvier 2025. Le schéma minimal est contrôlé pour les autres mois ; leur compatibilité ne peut être garantie sans exécution.
- Le fichier contient 56 colonnes nommées ; la présentation générale en annonce 55. `ETB_DCS_MCO` est conservée mais n’est pas interprétée par ce projet faute de définition dans le dictionnaire joint.
- Conversion à mémoire limitée par blocs, pas de cluster distribué. Aucun test sur un volume supérieur à la RAM n’est revendiqué.
- Audit de doublons exacts limité aux premières 100 000 lignes du mois. Aucune suppression de lignes ni déduplication métier automatique.
- Exécution séquentielle : ne pas lancer simultanément deux écritures sur la même racine. Pas de transaction atomique multi-fichiers ; un arrêt brutal entre publication et manifeste entraîne une reconstruction à la prochaine relance.
- Les journaux et les sorties locales ne doivent pas être exposés directement comme service public. Docker, GitLab CI, Kubernetes et déploiement relèvent du projet 4.
- R et Linux/WSL ne sont pas installés dans l’environnement de validation initial : les scripts correspondants sont fournis comme compléments, avec leur statut dans `docs/VALIDATION.md`.

## Source et licence

[Assurance Maladie — Open DAMIR](https://www.assurance-maladie.ameli.fr/etudes-et-donnees/open-damir-depenses-sante-interregimes), source déclarée SNDS, licence ouverte indiquée par le producteur. Le dictionnaire provient du lien « Descriptif des variables » de cette page. Les fichiers de provenance conservent les dates de récupération et empreintes. Aucune donnée personnelle de patient n’est ajoutée au projet.

## Expliquer le projet

> J’ai construit une chaîne reproductible sur des données publiques réelles de remboursements. Elle conserve la source, transforme les fichiers en données typées et contrôlées, puis produit des analyses SQL. J’ai vérifié les définitions métier et comparé les performances sur des résultats identiques. Ces données agrégées ne permettent pas de suivre des patients individuellement.

