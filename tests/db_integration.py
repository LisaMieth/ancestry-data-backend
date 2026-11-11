import unittest
import duckdb
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent


class TestDBViews(unittest.TestCase):
  def setUp(self) -> None:
    con = duckdb.connect(
      ROOT_DIR / "resources/sample.db", config={"allow_unsigned_extensions": "true"}
    )
    con.execute("LOAD duckpgq;")

    self.con = con

  def test_persons_in_linage(self):
    df = self.con.sql("SELECT * FROM silver.person").to_df()

    # Assert non-related spouse is not in lineage
    self.assertFalse(
      df.loc[df["full_name"] == "Marie Lechner"]["in_lineage"].item(), False
    )
    # Assert sibling is not in lineage
    self.assertFalse(
      df.loc[df["full_name"] == "Tobias Maier"]["in_lineage"].item(), False
    )

    # Assert root node is in lineage
    self.assertTrue(
      df.loc[df["full_name"] == "Melanie Maier"]["in_lineage"].item(), True
    )

  def test_dim_person_excludes_non_lineage(self):
    """dim_person should only contain in_lineage persons from silver.person."""
    df = self.con.sql("SELECT * FROM gold.dim_person").to_df()

    self.assertTrue((df["in_lineage"]).all())

    names = df["full_name"].to_list()
    self.assertNotIn("Marie Lechner", names)
    self.assertNotIn("Tobias Maier", names)
    self.assertIn("Melanie Maier", names)

    expected_count = self.con.sql(
      "SELECT COUNT(*) FROM silver.person WHERE in_lineage"
    ).fetchall()[0][0]
    self.assertEqual(len(df), expected_count)

  def test_distinct_last_names(self):
    """Assert that all expected normed last names are in dim_last_name. Last names of persons not
    in_lineage should be excluded"""
    df = self.con.sql(
      "SELECT * FROM gold.dim_last_name ORDER BY last_name_normed"
    ).to_df()

    self.assertListEqual(
      df["last_name_normed"].to_list(),
      sorted(["Huber", "Kratzer", "Maier", "Maier", "Schmidt"]),
    )

    self.assertNotIn("Lechner", df["last_name_normed"].to_list())

  def test_dim_last_name_fk(self):
    df = self.con.sql(
      "SELECT last_name_normed, COUNT(DISTINCT last_name_id) AS cnt FROM silver.person GROUP BY last_name_normed"
    ).to_df()

    self.assertEqual(df.loc[df["last_name_normed"] == "Huber"]["cnt"].item(), 1)
    self.assertEqual(df.loc[df["last_name_normed"] == "Schmidt"]["cnt"].item(), 1)
    # Assert that two distinct branches of "Maier" have different IDs
    self.assertEqual(df.loc[df["last_name_normed"] == "Maier"]["cnt"].item(), 2)

  def test_family_branches_roots(self):
    df = self.con.sql(
      "SELECT root_full_name, ancestor_full_name FROM gold.fct_family_branch"
    ).to_df()

    # Assert all root nodes appear
    self.assertSetEqual(
      set(df["root_full_name"].unique().tolist()),
      {
        "Melanie Maier",
        "Sabine Huber",
        "Brigitte Kratzer",
        "Margarethe Schmidt",
        "Kreszenz Maier",
      },
    )

  def test_family_branches_ancestors(self):
    df = self.con.sql(
      "SELECT root_full_name, COUNT(*) AS cnt FROM gold.fct_family_branch GROUP BY root_full_name"
    ).to_df()

    # Assert all 9 ancestors appear for this root node.
    self.assertEqual(df.loc[df["root_full_name"] == "Melanie Maier"]["cnt"].item(), 9)
