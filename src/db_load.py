from argparse import ArgumentParser
from pathlib import Path
import duckdb
from yaml import safe_load


ROOT_DIR = Path(__file__).parent.parent
SQL_DIR = ROOT_DIR / "src" / "sql"

RELATIONSHIP_FILE = ROOT_DIR / "output" / "relationships.csv"
PERSON_FILE = ROOT_DIR / "output" / "persons.csv"
CONFIG_FILE = ROOT_DIR / "config" / "dataset_config.yaml"


class NoRootNodeError(Exception):
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message


def read_config(config_path: Path) -> dict:
  """Read the config/dataset_config.yaml."""
  config = safe_load(config_path.read_text())

  return config


def get_root_node(config: dict) -> str:
  root = config.get("root_node")

  if root is None:
    raise NoRootNodeError("`root_node` key must be specified in config file.")

  return root


def persist_db(src_persons_file, src_relationships_file, db_file, config):
  db_file.parent.mkdir(parents=True, exist_ok=True)
  con = duckdb.connect(db_file, config={"allow_unsigned_extensions": "true"})
  con.execute("INSTALL duckpgq FROM community;")
  con.execute("LOAD duckpgq;")

  con.execute(
    f"CREATE OR REPLACE TABLE person_raw AS SELECT * FROM read_csv_auto('{src_persons_file}');"
  )
  con.execute(
    f"CREATE OR REPLACE TABLE relationship_raw AS SELECT * FROM read_csv_auto('{src_relationships_file}') WHERE parent_id IS NOT NULL;"
  )

  con.execute("""
    CREATE OR REPLACE PROPERTY GRAPH family_tree
    VERTEX TABLES (person_raw LABEL person)
    EDGE TABLES (
      relationship_raw
        SOURCE KEY (child_id) REFERENCES person_raw (id)
        DESTINATION KEY (parent_id) REFERENCES person_raw (id)
        LABEL rel
    );
  """)

  root_node = get_root_node(config)

  # Build lineage view
  lineage_query = get_formatted_query(
    SQL_DIR / "person_lineage.sql", {"root_node": root_node}
  )
  con.execute(lineage_query)

  # Build last name dimension
  dim_last_name_query = get_formatted_query(SQL_DIR / "dim_last_name.sql")
  con.execute(dim_last_name_query)

  con.close()


def strip_sql_comments(sql):
  """Drop `--` comment lines.

  duckpgq's GRAPH_TABLE preprocessor mis-parses statements that are preceded
  by line comments.
  """
  return "\n".join(
    line for line in sql.splitlines() if not line.strip().startswith("--")
  )


def get_formatted_query(path: Path, params: dict | None = None) -> str:
  """Read query from the given SQL file path and inject any required parameters."""
  sql = open(path).read()

  if params is not None:
    sql = f"{sql}".format(**params)

  sql = strip_sql_comments(sql)

  return sql


def run(db_file):
  config = read_config(CONFIG_FILE)

  persist_db(PERSON_FILE, RELATIONSHIP_FILE, db_file, config)

  print(f"Written to {db_file}.")


if __name__ == "__main__":
  relationship_file = ROOT_DIR / "output" / "relationships.csv"
  person_file = ROOT_DIR / "output" / "persons.csv"

  parser = ArgumentParser(description="Process data.")
  parser.add_argument(
    "-db",
    dest="db_file",
    required=False,
    help="Desired path to output database file. Default is `./assets/main.db`",
  )

  arg = parser.parse_args()

  db_file_name = (
    ROOT_DIR / "assets/main.db" if arg.db_file is None else ROOT_DIR / arg.db_file
  )

  run(db_file_name)
