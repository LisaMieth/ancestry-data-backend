import duckdb
import pandas as pd


def persist_db(src_file, db_file):
  con = duckdb.connect(db_file)
  # Increase sample size to avoid DuckDB guessing the wrong type because of null values.
  con.execute("SET GLOBAL pandas_analyze_sample=10000")
  df = pd.read_csv(src_file)

  con.execute("CREATE TABLE ancestry AS SELECT * FROM df")
  con.execute("INSERT INTO ancestry SELECT * FROM df")

  con.close()


if __name__ == '__main__':
  input_file = 'assets/result.csv'
  db_file_name = 'assets/main.db'

  persist_db(input_file, db_file_name)

  print('DONE.')
