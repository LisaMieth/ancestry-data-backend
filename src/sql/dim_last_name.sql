CREATE OR REPLACE TABLE dim_last_name AS
SELECT
    last_name_id AS id, 
    last_name_normed
FROM person
WHERE in_lineage
GROUP BY last_name_id, last_name_normed;