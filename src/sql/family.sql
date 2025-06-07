-- Query to only select direct ancestors and exclude any non-related spouses and half-siblings of ancestors.
-- Build rest of queries on top of this.
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
),
points AS (
	SELECT 
	  *,
	  ST_POINT(longitude, latitude) AS pnt,
	  random() * 200.0 AS ang,
	  random() * 0.02 AS rad,
	  ROW_NUMBER () OVER (PARTITION BY place, longitude, latitude) AS row_num
	FROM parent_names
)

SELECT 
  * EXCLUDE (ang, rad, row_num),
  CASE WHEN row_num > 1 
  THEN ST_AsGeoJSON(ST_POINT(ST_Y(pnt) + rad*COS(ang), ST_X(pnt) + rad*SIN(ang))) 
  ELSE ST_AsGeoJSON(pnt) END AS point
FROM points