import duckdb

con = duckdb.connect(config={"allow_unsigned_extensions": "true"})
print('DuckDB version:', duckdb.__version__)

con.install_extension('duckpgq', repository='community')
con.load_extension('duckpgq')

result = con.sql("SELECT 'duckpgq loaded ok'").fetchone()
print(result)