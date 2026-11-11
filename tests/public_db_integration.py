import unittest
import duckdb
from pathlib import Path
from yaml import safe_load

ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "public_interface.yaml"


def load_table_contracts() -> dict[str, dict]:
  """Derive table -> {schema, columns} straight from the interface contract,
  so this test validates the built DB against the real source of truth
  instead of a hand-copied duplicate of it."""
  config = safe_load(CONFIG_FILE.read_text())

  return {
    table_name: {"schema": spec["schema"], "columns": set(spec["columns"])}
    for table_name, spec in config["tables"].items()
  }


class TestPublicDBViews(unittest.TestCase):
  def setUp(self) -> None:
    self.table_contracts = load_table_contracts()
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

    self.assertSetEqual(tables, set(self.table_contracts.keys()))

  def test_table_columns_match_contract(self):
    for table_name, contract in self.table_contracts.items():
      columns = {
        row[0] for row in self.con.execute(f"DESCRIBE {table_name};").fetchall()
      }

      self.assertSetEqual(
        columns, contract["columns"], f"columns mismatch for {table_name}"
      )

  def test_row_counts_match_source(self):
    for table_name, contract in self.table_contracts.items():
      public_count = self.con.sql(f"SELECT COUNT(*) FROM {table_name};").fetchall()[0][
        0
      ]
      main_count = self.con.sql(
        f"SELECT COUNT(*) FROM main_db.{contract['schema']}.{table_name};",
      ).fetchall()[0][0]

      self.assertEqual(public_count, main_count, f"row count mismatch for {table_name}")
