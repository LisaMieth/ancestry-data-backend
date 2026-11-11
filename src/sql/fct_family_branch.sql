-- Family name/branch view (see SPEC.md).
-- For every last-name branch (see dim_last_name / person.last_name_id), the
-- root node is the branch member who is never a parent of another member of
-- the *same* branch -- i.e. the most recent link in that surname's chain,
-- where the surname either changes (marriage) or the chain ends (the
-- configured root_node). Returns that root plus all of its direct ancestors
-- via the `family_tree` property graph.
--
-- NOTE: GRAPH_TABLE must be the entire body of its own CTE -- joining it
-- inline (e.g. `JOIN GRAPH_TABLE(...) AS x ON TRUE`) fails to parse.
CREATE OR REPLACE TABLE fct_family_branch AS
WITH within_branch_parents AS (
  SELECT DISTINCT r.parent_id, parent.last_name_id
  FROM relationship_raw r
  JOIN person parent ON parent.id = r.parent_id
  JOIN person child ON child.id = r.child_id
  WHERE parent.last_name_id = child.last_name_id
),
roots AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY last_name_id
      ORDER BY date_birth DESC NULLS LAST
    ) AS rn
  FROM person
  WHERE in_lineage
    AND id NOT IN (SELECT parent_id FROM within_branch_parents)
),
root AS (
  SELECT * EXCLUDE (rn)
  FROM roots
  WHERE rn = 1
),
ancestors AS (
  FROM GRAPH_TABLE (family_tree
      MATCH p = ANY SHORTEST (a:person)-[r:rel]->+(b:person)
      WHERE a.id IN (SELECT id FROM root)
      COLUMNS (
        a.id AS root_id,
        b.id AS id,
        b.full_name AS full_name,
        b.place AS location,
        CASE WHEN 
          b.latitude IS NULL OR b.longitude IS NULL THEN NULL
          ELSE [b.latitude, b.longitude] 
        END AS geolocation,
        COALESCE(
          CAST(b.date_birth AS DATE),
          CAST(b.date_marriage_1 AS DATE),
          CAST(b.date_death AS DATE)
        ) AS date_ref,
        path_length(p) AS hops
      )
  )
)
SELECT
  root.id AS root_id,
  root.full_name AS root_full_name,
  root.last_name_id,
  root.place AS root_location,
  COALESCE(
    CAST(root.date_birth AS DATE),
    CAST(root.date_marriage_1 AS DATE),
    CAST(root.date_death AS DATE)
  ) AS root_date_ref,
  ancestors.id AS ancestor_id,
  ancestors.full_name AS ancestor_full_name,
  ancestors.location AS ancestor_location_name,
  ancestors.geolocation AS ancestor_geolocation,
  ancestors.date_ref AS ancestor_date_ref,
  ancestors.hops AS ancestor_hops
FROM root
LEFT JOIN ancestors ON ancestors.root_id = root.id
ORDER BY root.full_name, ancestors.hops
