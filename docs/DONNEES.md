# Source, périmètre et décisions métier

Source principale : [Open DAMIR, Assurance Maladie](https://www.assurance-maladie.ameli.fr/etudes-et-donnees/open-damir-depenses-sante-interregimes). Catalogue 2025 : [fichiers mensuels](https://open-data-assurance-maladie.ameli.fr/depenses/download.php?Annee=2025&Dir_Rep=Open_DAMIR). Dictionnaire : [descriptif officiel](https://www.assurance-maladie.ameli.fr/content/descriptif-des-variables-de-la-serie-open-damir-base-complete). Consultés le 12 septembre 2026.

## Niveau d’observation

La base est issue du SNDS, mais sa diffusion est agrégée. La présence d’un code de tranche d’âge ou de région ne permet pas d’identifier un bénéficiaire. Il n’y a pas de clé patient permettant de construire une séquence individuelle. `count(*)` compte les lignes d’agrégats ; il ne compte pas des patients.

Le mois du fichier et `FLX_ANN_MOI` désignent la période de traitement/remboursement. Le dictionnaire décrit plus précisément `FLX_ANN_MOI` comme une date technique de chargement des flux. `SOI_ANN` et `SOI_MOI` décrivent la période des soins et sont conservés séparément. Ce projet n’assimile pas ces deux temporalités.

## Indicateurs retenus

| Variable | Usage |
|---|---|
| `FLT_REM_MNT` | Montants préfiltrés de remboursement de la part légale |
| `FLT_PAI_MNT` | Dépenses préfiltrées |
| `FLT_DEP_MNT` | Dépassements préfiltrés ; ne pas les assimiler à tout reste à charge |
| `FLT_ACT_QTE` | Quantité préfiltrée ; ne pas additionner des prestations hétérogènes pour compter des patients |
| `PRS_REM_MNT` | Montants bruts, parts légales et supplémentaires ; conservés pour contrôle |
| `PRS_REM_TYP` | Types 0 et 1 pour la part légale dans la définition du dictionnaire |
| `TOP_PS5_TRG` | Valeur 1 pour se rapprocher du périmètre de la statistique mensuelle du producteur |

Les dépenses et volumes bruts ont des règles de filtrage spécifiques. Les analyses utilisent les indicateurs FLT, sans ajouter PRS et FLT entre eux. Pour les types de remboursement connus, le remboursement préfiltré est comparé au montant brut lorsque le type est 0 ou 1, sinon zéro. Toute différence sur ce périmètre bloque la publication. Le code 99 signifie « valeur inconnue » : le filtre ne peut pas être reconstruit sur ces lignes. Elles sont comptées séparément et les indicateurs FLT du producteur sont conservés. Un code absent de la nomenclature validée bloque le traitement. Ce contrôle ne constitue pas une règle universelle applicable à toute future version de la source.

Le rapport principal présente la somme nette sur toutes les lignes du fichier chargé. La requête `06_scope.sql` sépare les modalités de `TOP_PS5_TRG`. Aucun de ces résultats n’est présenté comme le total exhaustif des dépenses de santé nationales.

## Nettoyage conservateur

- Suppression des espaces de bord et conversion d’une chaîne vide en valeur nulle.
- Suppression uniquement de la colonne sans nom créée par le séparateur terminal, après vérification qu’elle est vide.
- Conservation de toutes les colonnes nommées, des codes spéciaux et des zéros initiaux.
- Conversion des indicateurs en décimal exact ; acceptation du point ou de la virgule décimale et de six décimales au maximum. Une précision supérieure ou une valeur non numérique bloque la conversion.
- Conservation des nombres négatifs : leur signe ne démontre pas une erreur. Il peut être nécessaire d’étudier les régularisations et le contexte de liquidation avec le producteur.
- Pas d’imputation arbitraire des nombres d’actes manquants. Le dictionnaire précise que le dénombrement n’est pas remonté par tous les régimes.
- Pas de suppression automatique des doublons, car une égalité apparente ne prouve pas un doublon métier.

## Nomenclatures

`references/variables.json` et `references/modalites.json` sont extraits du classeur officiel joint. Les libellés suivent cette version du producteur : les noms de certaines régions sont historiques et Provence-Alpes-Côte d’Azur et Corse forment une même modalité. Le code 99 représente ici une région inconnue. Il serait incorrect d’appliquer sans vérification une liste de régions provenant d’une autre source.

La colonne `ETB_DCS_MCO`, présente dans janvier 2025, n’a pas de définition dans le dictionnaire joint. Elle est préservée et exclue des interprétations. Le manifeste enregistre la liste réelle des colonnes.

## Gouvernance et limites

La page source indique une Licence ouverte. Conserver l’attribution au producteur, la date, le périmètre et les transformations. Les empreintes SHA-256 locales détectent les modifications après récupération ; elles ne remplacent pas une signature cryptographique fournie par le producteur.

Ce projet travaille sur des fichiers publics agrégés. Il ne démontre pas la maîtrise des procédures d’accès aux données individuelles du SNDS, ni la conformité d’un traitement futur de données personnelles. Une pseudonymisation ne doit pas être confondue avec une anonymisation. Pour préparer ce sujet : [CNIL, présentation du SNDS](https://www.cnil.fr/fr/snds-systeme-national-des-donnees-de-sante).

## Références techniques

- [Apache Arrow : lecture CSV incrémentale](https://arrow.apache.org/docs/python/csv.html)
- [Polars : lecture CSV et évaluation différée](https://docs.pola.rs/api/python/stable/reference/api/polars.read_csv.html)
- [DuckDB : import CSV](https://duckdb.org/docs/current/data/csv/overview)

L’utilisation de `lazy()` après lecture est ici limitée à un petit bloc déjà chargé : le fichier complet n’est pas matérialisé dans une DataFrame.
