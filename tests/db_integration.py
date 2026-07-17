import unittest
import duckdb

from src.queries import family_branch


class TestDBViews(unittest.TestCase):
  def setUp(self) -> None:
    con = duckdb.connect(
      "./resources/sample.db", config={"allow_unsigned_extensions": "true"}
    )
    con.execute("LOAD duckpgq;")

    self.con = con

  # def test_distinct_families(self):
  #     sql = open("src/sql/distinct_families.sql").read()
  #     result = self.con.sql(sql).df()

  #     self.assertListEqual(
  #         result["family_name"].to_list(),
  #         ["Maier", "Huber", "Schmidt", "Kratzer"]
  #     )

  def test_persons_in_linage(self):
    df = self.con.sql("SELECT * FROM person").to_df()

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

  def test_distinct_last_names(self):
    """Assert that all expected normed last names are in dim_last_name. Last names of persons not
    in_lineage should be excluded"""
    df = self.con.sql("SELECT * FROM dim_last_name ORDER BY last_name_normed").to_df()

    self.assertListEqual(
      df["last_name_normed"].to_list(),
      sorted(["Huber", "Kratzer", "Maier", "Maier", "Schmidt"]),
    )

    self.assertNotIn("Lechner", df["last_name_normed"].to_list())

  def test_dim_last_name_fk(self):
    df = self.con.sql(
      "SELECT last_name_normed, COUNT(DISTINCT last_name_id) AS cnt FROM person GROUP BY last_name_normed"
    ).to_df()

    self.assertEqual(df.loc[df["last_name_normed"] == "Huber"]["cnt"].item(), 1)
    self.assertEqual(df.loc[df["last_name_normed"] == "Schmidt"]["cnt"].item(), 1)
    # Assert that two distinct branches of "Maier" have different IDs
    self.assertEqual(df.loc[df["last_name_normed"] == "Maier"]["cnt"].item(), 2)

  # def test_family_branch_view(self):
  #     result = family_branch(self.con, "Maier")
  #     print(result)
  #     self.assertEqual(result.loc[0, "root_id"], "@I8@")
  #     self.assertEqual(result.loc[0, "root_full_name"], "Tobias Maier")

  #     ancestor_ids = {a["id"] for a in result.loc[0, "ancestors"]}
  #     self.assertSetEqual(
  #         ancestor_ids,
  #         {"@I2@", "@I3@", "@I4@", "@I5@", "@I6@", "@I7@", "@I11@", "@I12@"},
  #     )
