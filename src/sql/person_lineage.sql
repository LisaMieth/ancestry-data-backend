-- Creates the final `person` table from `person_raw`, adding:
--   - in_lineage: true for the configured root_node (see
--     config/dataset_config.yaml) and their direct ancestors via the
--     `family_tree` property graph, false otherwise (non-ancestral spouses,
--     siblings/half-siblings of ancestors, and other side lineages).
--   - last_name_id: a foreign key identifying the (last_name_normed, family
--     branch) a person belongs to. Two persons only share a last_name_id if
--     they're connected via an unbroken chain of parent/child edges where
--     every person along the chain shares the same last_name_normed --
--     unrelated branches that happen to normalise to the same surname (see
--     TODO.md) get distinct ids. This is used as the id in dim_last_name.
--
-- NOTE: duckpgq does not support bound parameters in statements containing
-- GRAPH_TABLE, so {root_node} must be substituted by the caller.
-- NOTE: GRAPH_TABLE must be the entire body of its own CTE -- joining it
-- inline (e.g. `JOIN GRAPH_TABLE(...) AS x ON TRUE`) fails to parse.
CREATE OR REPLACE TABLE person AS
WITH RECURSIVE
root AS (
  SELECT id FROM person_raw WHERE full_name = '{root_node}'
),
ancestors AS (
  FROM GRAPH_TABLE (family_tree
      MATCH p = ANY SHORTEST (a:person)-[r:rel]->+(b:person)
      WHERE a.id = (SELECT id FROM root)
      COLUMNS (b.id AS id)
  )
),
-- Parent/child edges where both sides share the same last_name_normed, i.e.
-- the surname was carried over rather than acquired by marriage/normalising
-- coincidence.
same_surname_edges AS (
  SELECT r.child_id, r.parent_id
  FROM relationship_raw r
  JOIN person_raw child ON child.id = r.child_id
  JOIN person_raw parent ON parent.id = r.parent_id
  WHERE parent.last_name_normed = child.last_name_normed
),
-- For every person, walk up same_surname_edges to the topmost ancestor of
-- their unbroken same-surname chain -- that ancestor's id anchors the branch.
branch_anchor AS (
  SELECT p.id AS id, p.id AS anchor_id
  FROM person_raw p
  WHERE p.id NOT IN (SELECT child_id FROM same_surname_edges)

  UNION ALL

  SELECT e.child_id AS id, ba.anchor_id AS anchor_id
  FROM same_surname_edges e
  JOIN branch_anchor ba ON ba.id = e.parent_id
),
-- One random id per distinct branch anchor (not per person).
branch_ids AS (
  SELECT anchor_id, gen_random_uuid() AS last_name_id
  FROM (SELECT DISTINCT anchor_id FROM branch_anchor)
)
SELECT
  person_raw.*,
  person_raw.id IN (SELECT id FROM root) OR person_raw.id IN (SELECT id FROM ancestors) AS in_lineage,
  branch_ids.last_name_id AS last_name_id
FROM person_raw
JOIN branch_anchor ON branch_anchor.id = person_raw.id
JOIN branch_ids ON branch_ids.anchor_id = branch_anchor.anchor_id;
