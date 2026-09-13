# Validation et périmètre de la livraison

## Vérifications automatisées

23 tests hors réseau ont réussi sous Windows avec Python 3.12. Le résultat machine est conservé dans `reports/tests.xml`.

Ils couvrent :

- les mois invalides et les colonnes absentes ;
- la conversion exacte des montants, les virgules, espaces, valeurs nulles et nombres négatifs ;
- le rejet de nombres illisibles et d’une précision supérieure à six décimales ;
- la conservation des codes et la suppression de la colonne terminale vide ;
- l’intégrité de l’archive et les téléchargements incomplets ou refusés ;
- la relance sans duplication et la conservation de la partition précédente en cas d’échec ;
- le contrôle des remboursements sur les types connus et le traitement explicite du type inconnu 99 ;
- l’usage des indicateurs préfiltrés dans les SQL et une jointure qui conserve les totaux ;
- l’équivalence des cinq méthodes du benchmark sur un petit jeu contrôlé.
- la génération du rapport à partir de montants décimaux exacts.

Les données des tests sont fictives et servent à provoquer des cas précis. Elles ne figurent pas dans les analyses métier.

L’installation éditable a été exécutée ; `pip check` n’a détecté aucune dépendance incompatible. Un package wheel a été construit et la présence des sept fichiers SQL a été vérifiée.

Le rapport HTML a été ouvert dans le navigateur et contrôlé visuellement. Les résultats du benchmark et les libellés officiels y sont lisibles. Le lanceur PowerShell est utilisé pour la validation finale de la commande complète ; les logs conservent le statut de cette exécution.

## Vérification sur données réelles

Les preuves d’exécution sont dans :

| Fichier | Preuve |
|---|---|
| `data/raw/A202501.csv.gz.json` | Origine, téléchargement et SHA-256 de l’archive complète |
| `data/manifests/202501.json` | Version du pipeline, lignes, schéma, tailles et SHA-256 du Parquet |
| `reports/quality/202501.json` | Contrôles sur le mois complet et diagnostics |
| `reports/source_verification.json` | Comparaison indépendante CSV/Parquet du nombre de lignes et de sept sommes |
| `reports/analyses/results.json` | Résultats des sept requêtes DuckDB |
| `reports/benchmark.json` | Mesures individuelles, environnement et équivalence exacte |
| `reports/RESULTATS.md` | Résumé lisible des résultats |

L’audit de doublons est limité aux 100 000 premières lignes. Les mesures du benchmark sont limitées au million de lignes choisi ; les analyses et contrôles principaux portent sur le mois entier.

## Incidents résolus pendant la construction

1. **Consommation mémoire excessive de la conversion initiale.** Le processus a été arrêté ; la version livrée utilise un lecteur Arrow incrémental et un nettoyage Polars par bloc. Le mot « streaming » ne constitue pas, à lui seul, une garantie sur le pic mémoire d’un plan de calcul.
2. **Interprétation trop stricte du type de remboursement inconnu.** Les écarts du premier contrôle concernaient le code 99, documenté comme inconnu. La règle finale vérifie les types connus et expose explicitement la population dont le filtre ne peut pas être reconstruit. Les indicateurs officiels sont conservés.
3. **Séparateur terminal du CSV.** Le parseur peut renommer une colonne vide. La version finale lui donne un nom interne explicite avant de vérifier qu’elle est vide et de la retirer.

## Ce qui n’est pas revendiqué

- Pas de validation sous R/RStudio : R n’est pas installé ici. Le script R est un complément à exécuter dans cet environnement.
- Pas d’exécution Bash sous Linux/WSL : cet environnement n’est pas installé ici. Le lanceur Bash est fourni.
- Pas de Docker, GitLab CI/CD, Kubernetes ou hébergement : ils relèvent du projet 4.
- Pas de traitement distribué, de test au-delà de la RAM, de validation clinique ou d’expérience de production.
- Pas de garantie de performance sur une autre machine, ni de compatibilité de tous les mois historiques sans vérification.

Le projet constitue une base de portfolio exécutable, accompagnée de preuves et de limites, et non un système de production certifié.

## Chiffres de la conversion validée

Janvier 2025 : 36 640 259 lignes et 56 colonnes nommées. CSV brut : 5 920 554 406 octets ; gzip officiel : 973 594 858 octets ; Parquet : 1 066 559 487 octets. La conversion par blocs a pris 321,516 secondes, hors téléchargement, décompression et contrôle final.

Parquet réduit la taille par rapport au texte non compressé ; il est légèrement plus gros que le gzip officiel. Sa valeur tient aussi au typage, à la lecture de colonnes ciblées et à son usage analytique. Les points de mesure ponctuels observés pendant la conversion restaient autour de 1 Go de mémoire résidente ; aucun pic exhaustif du pipeline complet n’a été instrumenté.
