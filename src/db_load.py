import duckdb
import pandas as pd


def persist_db(src_file, db_file):
  con = duckdb.connect(db_file)
  # Increase sample size to avoid DuckDB guessing the wrong type because of null values.
  con.execute("SET GLOBAL pandas_analyze_sample=10000")
  # Install & load DuckDB spatial extension
  con.execute("INSTALL spatial;")
  con.execute("LOAD spatial;")

  df = pd.read_csv(src_file)
  sql_query = open('./src/sql/family.sql', 'r').read()

  # Recreate tables.
  con.execute("DROP TABLE IF EXISTS ancestry")
  con.execute("DROP TABLE IF EXISTS family")

  # Insert new data into ancestry src table.
  con.execute("CREATE TABLE ancestry AS SELECT * FROM df")

  # Query to only select direct ancestors and exclude any non-related spouses and half-siblings of ancestors.
  df_fam = pd.read_sql(sql_query, con)

  # Create new family table from family query.
  con.execute("CREATE TABLE family AS SELECT * FROM df_fam")

  con.close()


if __name__ == '__main__':
  input_file = 'assets/result.csv'
  db_file_name = 'assets/main.db'

  persist_db(input_file, db_file_name)

  print(f"Written {input_file} to {db_file_name}.")
