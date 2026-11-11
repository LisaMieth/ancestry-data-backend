import unittest
import duckdb
from pathlib import Path
from yaml import safe_load

ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "public_interface.yaml"


def fetch_scalar(con, query: str):
  """Run a query expected to return exactly one row/column and return that value."""
  row = con.execute(query).fetchone()
  assert row is not None, f"query returned no rows: {query}"

  return row[0]


def load_expected_columns() -> dict[str, set[str]]:
  """Derive table -> expected columns straight from the interface contract,
  so this test validates the built DB against the real source of truth
  instead of a hand-copied duplicate of it."""
  config = safe_load(CONFIG_FILE.read_text())

  return {
    table_name: set(spec["columns"]) for table_name, spec in config["tables"].items()
  }


class TestPublicDBViews(unittest.TestCase):
  def setUp(self) -> None:
    self.expected_columns = load_expected_columns()
    self.con = duckdb.connect(ROOT_DIR / "resources/sample_public.db")
    self.con.execute(
      f"ATTACH '{ROOT_DIR / 'resources/sample.db'}' AS main_db (READ_ONLY);"
    )

  def test_only_configured_tables_exist(self):
    tables = {
      row[0]
      for row in self.con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'sample_public'"
      ).fetchall()
    }

    self.assertSetEqual(tables, set(self.expected_columns.keys()))

  def test_table_columns_match_contract(self):
    for table_name, expected_columns in self.expected_columns.items():
      columns = {
        row[0] for row in self.con.execute(f"DESCRIBE {table_name};").fetchall()
      }

      self.assertSetEqual(
        columns, expected_columns, f"columns mismatch for {table_name}"
      )

  def test_row_counts_match_source(self):
    for table_name in self.expected_columns:
      public_count = fetch_scalar(self.con, f"SELECT COUNT(*) FROM {table_name};")
      main_count = fetch_scalar(self.con, f"SELECT COUNT(*) FROM main_db.{table_name};")

      self.assertEqual(public_count, main_count, f"row count mismatch for {table_name}")
