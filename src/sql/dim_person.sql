-- Person Dimension (see SPEC.md). All persons in the lineage for the
-- configured root_node; side-lineage persons (non-ancestrial spouses,
-- siblings, etc. -- see silver.person.in_lineage) are excluded.
CREATE OR REPLACE TABLE gold.dim_person AS
SELECT *
FROM silver.person
WHERE in_lineage;
