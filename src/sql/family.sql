-- Query to only select direct ancestors and exclude any non-related spouses and half-siblings of ancestors.
-- Set this as new DB table to build rest of queries on top of.
WITH RECURSIVE parent_names AS (
    -- Root node, i.e. me
    SELECT 
      *
    FROM ancestry
    WHERE full_name = 'Lisa Mieth'
UNION ALL
    SELECT 
      ancestry.*
    FROM ancestry
    JOIN parent_names
    ON (
    	ancestry.reference = parent_names.mother_reference
    	OR ancestry.reference = parent_names.father_reference
    )
)

SELECT * FROM parent_names