from argparse import ArgumentParser
from pathlib import Path
import duckdb
from yaml import safe_load


ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "public_interface.yaml"


class InvalidPublicConfigError(Exception):
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message


def read_config(config_path: Path) -> dict:
  """Read the config/public_interface.yaml."""
  config = safe_load(config_path.read_text())

  return config


def get_table_contracts(config: dict) -> dict[str, list[str]]:
  """Validate and extract the table -> approved columns mapping."""
  tables = config.get("tables")

  if not tables:
    raise InvalidPublicConfigError("`tables` key must be specified in config file.")

  contracts = {}

  for table_name, spec in tables.items():
    columns = (spec or {}).get("columns")

    if not columns:
      raise InvalidPublicConfigError(
        f"Table `{table_name}` must specify a non-empty `columns` list."
      )

    contracts[table_name] = columns

  return contracts


def validate_columns(con, table_name: str, columns: list[str]) -> None:
  """Raise if a configured column doesn't exist in the source table."""
  existing = {row[0] for row in con.execute(f"DESCRIBE src.{table_name};").fetchall()}
  missing = [c for c in columns if c not in existing]

  if missing:
    raise InvalidPublicConfigError(
      f"Columns {missing} configured for `{table_name}` do not exist in the source table."
    )


def persist_public_db(src_db_file: Path, public_db_file: Path, config: dict) -> None:
  public_db_file.parent.mkdir(parents=True, exist_ok=True)
  table_contracts = get_table_contracts(config)

  con = duckdb.connect(public_db_file)
  con.execute(f"ATTACH '{src_db_file}' AS src (READ_ONLY);")

  for table_name, columns in table_contracts.items():
    validate_columns(con, table_name, columns)
    column_list = ", ".join(columns)
    con.execute(
      f"CREATE OR REPLACE TABLE {table_name} AS SELECT {column_list} FROM src.{table_name};"
    )

  con.execute("DETACH src;")
  con.close()


def run(src_db_file: Path, public_db_file: Path) -> None:
  config = read_config(CONFIG_FILE)

  persist_public_db(src_db_file, public_db_file, config)

  print(f"Written public DB to {public_db_file}.")


if __name__ == "__main__":
  parser = ArgumentParser(description="Build the public-facing DB from the main DB.")
  parser.add_argument(
    "-src-db",
    dest="src_db_file",
    required=False,
    help="Path to the source (main) database. Default is `./assets/main.db`",
  )
  parser.add_argument(
    "-db",
    dest="db_file",
    required=False,
    help="Desired path to output public database file. Default is `./assets/public.db`",
  )

  arg = parser.parse_args()

  src_db_file_name = (
    ROOT_DIR / "assets/main.db"
    if arg.src_db_file is None
    else ROOT_DIR / arg.src_db_file
  )
  db_file_name = (
    ROOT_DIR / "assets/public.db" if arg.db_file is None else ROOT_DIR / arg.db_file
  )

  run(src_db_file_name, db_file_name)
