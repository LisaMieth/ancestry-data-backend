import json
import re
from datetime import datetime, date
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
    config = safe_load(data)

    return config


def build_column_mapping(config: dict) -> dict:
  """Extract target_col names into column list."""
  _columns = config.get("columns")

  if _columns is None:
    raise InvalidConfigFormatError("Config file must include top level key `columns`.")

  mapping = {}

  for col in _columns:
    src = col.get("src_col")
    trgt = col.get("target_col")

    if src is None or trgt is None:
      raise InvalidConfigFormatError(
        "`target_col` and `src_col` keys must be specified."
      )

    mapping[src] = trgt

  return mapping


def read_data(file_name: str, mapping: dict, dtypes) -> pd.DataFrame:
  df = pd.read_csv(
    file_name,
    delimiter="\t",
    quotechar='"',
    encoding="utf-16",
    dtype=dtypes,
    keep_default_na=False,
  )

  df = df.rename(columns=mapping)

  return df


def run(config_path: str, data_file_path: str) -> None:
  config = read_column_config(config_path)
  col_mapping = build_column_mapping(config)
  dtypes = {x: "string" for x in col_mapping.keys()}

  df = read_data(data_file_path, col_mapping, dtypes)


if __name__ == "__main__":
  config_path = "config/column_config.yaml"
  data_file = "data/SampleData.csv"

  run(config_path, data_file)
