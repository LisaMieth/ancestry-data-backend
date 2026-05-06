import json
from yaml import safe_load
import pandas as pd


class InvalidConfigFormatError(Exception):
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message


def read_column_config(config_path: str) -> dict:
  """Read provided YML config file into dictionary."""
  with open(config_path, "r") as f:
    data = f.read()
    config= safe_load(data)
    
    return config
  
  
def get_column_names(config: dict) -> list[str]:
  """Extract target_col names into column list."""
  _columns = config.get("columns")

  if _columns is None:
    raise InvalidConfigFormatError("Config file must include top level key `columns`.")
  
  columns = []

  for col in _columns:
    trgt = col.get("target_col")

    if trgt is None:
      raise InvalidConfigFormatError("`target_col` property must be specified.")
    
    columns.append(trgt)

  return columns


def read_data(file_name: str, cols: list[str], dtypes) -> pd.DataFrame:
  df = pd.read_csv(file_name, delimiter="\t", header=None, names=cols, quotechar="\"", encoding="utf-16", dtype=dtypes)
  
  return df


def run(config_path: str, data_file_path: str) -> None:
    config = read_column_config(config_path)
    cols = get_column_names(config)
    dtypes = {x: "string" for x in cols}

    df = read_data(data_file_path, cols, dtypes)


if __name__ == "__main__":
  config_path = "config/column_config.yaml"
  data_file = "data/Combined-All-11-23-neu.csv"

  run(config_path, data_file)