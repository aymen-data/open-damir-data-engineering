-- FLT : indicateurs préfiltrés par le producteur pour éviter les doubles comptes.
-- Sommes nettes sur le périmètre du fichier, pas une estimation de toutes les dépenses nationales.
SELECT FLX_ANN_MOI AS mois_traitement,
       count(*) AS lignes_agregees,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur,
       sum(FLT_PAI_MNT) AS depense_prefiltree_eur,
       sum(FLT_DEP_MNT) AS depassement_prefiltre_eur,
       sum(FLT_ACT_QTE) AS quantite_prefiltree,
       count(*) FILTER (WHERE FLT_REM_MNT < 0) AS lignes_remboursement_negatif
FROM remboursements
GROUP BY FLX_ANN_MOI ORDER BY FLX_ANN_MOI;
