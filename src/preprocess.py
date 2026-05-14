import json
import re
from time import sleep
from datetime import datetime, date
from yaml import safe_load
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geopy.location import Location
from argparse import ArgumentParser


class InvalidConfigFormatError(Exception):
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message


def read_config(config_path: str) -> dict:
  """Read provided YML config file into dictionary."""
  with open(config_path, "r") as f:
    data = f.read()
    config = safe_load(data)

    return config


def safe_get(config: dict, key: str):
  value = config.get(key)

  if value is None:
    raise InvalidConfigFormatError(f"Config file must include key `{key}`.")

  return value


def build_column_mapping(config: dict) -> tuple[dict, list]:
  """Extract target_col names into column list."""
  _columns = safe_get(config, "columns")
  mapping = {}
  excluded = []

  for col in _columns:
    src = col.get("src_col")
    trgt = col.get("target_col")
    include = col.get("include", True)

    if src is None or trgt is None:
      raise InvalidConfigFormatError(
        "`target_col` and `src_col` keys must be specified."
      )

    if not include:
      excluded.append(trgt)

    mapping[src] = trgt

  return mapping, excluded


def read_data(file_name: str, mapping: dict, dtypes, excluded: list) -> pd.DataFrame:
  """Read CSV file into dataframe."""
  df = pd.read_csv(
    file_name,
    delimiter="\t",
    quotechar='"',
    encoding="utf-16",
    dtype=dtypes,
    na_values=[""],
    keep_default_na=False,
  )

  # Rename columns after reading to avoid conflicts with column order
  df = df.rename(columns=mapping)
  df = df.replace({np.nan: None})
  df = df.drop(
    excluded, axis=1, errors="ignore"
  )  # ignore errors in case any columns don't exist

  return df


def clean_date(value: str | None) -> date | None:
  """Casts date strings to formatted datetime values for comparison."""
  if not value or value == "" or value == "?":
    return None

  year_match = re.search(r"\d{4}", value)

  if year_match:
    year = int(year_match.group())
    value = f"01.01.{year}"
  else:
    return None

  return datetime.strptime(value.strip(), "%d.%m.%Y").date()


def clean_data(df: pd.DataFrame, date_cols: list) -> pd.DataFrame:
  """Clean date columns, add birth & death year, clean last name."""
  for col in date_cols:
    # Skip any non-existent columns
    if col not in df.columns:
      continue

    df[col] = df[col].apply(clean_date)

  df["year_birth"] = df["date_birth"].apply(lambda x: str(x.year) if x else None)
  df["year_death"] = df["date_death"].apply(lambda x: str(x.year) if x else None)

  df["last_name"] = df["last_name"].apply(lambda x: re.sub(r"\(|\)|\?", "", x))

  return df


def generate_possibilities(value):
  """Returns list of possible location values from given input value."""
  possibilities = [value]

  # A value can contain a broader parent location - Poigham (Karpfham)
  if "(" in value:
    outside = re.findall(r"(.*?)\(.*\)+", value)
    inside = re.findall(r"\((.*?)\)", value)

    possibilities.append(outside[0].strip())
    possibilities.append(inside[0].strip())

  return possibilities


def geocode(geocoder: Nominatim, elem: str) -> Location | None:
  """Attempts to find geocode for the given value or its possibilities."""
  if elem == "" or elem is None:
    return None

  # Lookup entire location as well as possible separated values i.e.
  # elem before () and inside ()
  possibilities = generate_possibilities(elem)
  location = None

  for item in possibilities:
    if location:
      break

    try:
      location = geocoder.geocode(f"{item}, Germany", language="DE")  # type: ignore
    except GeocoderTimedOut:
      sleep(5)
      # Add for retry
      possibilities.append(item)  # pylint: disable=modified-iterating-list

  return location  # type: ignore


def lookup_location(
  row: pd.Series, geocoder: Nominatim, place_map: dict, cols: list
) -> tuple:
  """For the given row in a dataframe, get coordinates from cache or lookup via geocde()."""
  place = row[cols].bfill().iloc[0]
  place = place.strip() if place is not None else place
  location = place_map.get(place, None)
  latitude, longitude = None, None

  if location:
    latitude = location["latitude"]
    longitude = location["longitude"]

  else:
    location = geocode(geocoder, place)

    if location:
      latitude = location.latitude
      longitude = location.longitude
      place_map[place] = {
        "latitude": latitude,
        "longitude": longitude,
        "location": location.address,
      }

  return (place, latitude, longitude)


def remove_sensitive_data(df: pd.DataFrame, cutoff_date, date_cols: list):
  """Remove any rows with date_birth after the cutoff and nullify values after cuttoff."""
  # Remove persons born after cut-off date
  cutoff = cutoff_date
  if type(cutoff_date) == str:
    cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d").date()

  df = df[~df["date_birth"].gt(cutoff)]

  # Remove any sensitive dates
  df[date_cols] = df[date_cols].where(df[date_cols] <= cutoff, other=None)

  # Remove any sensitive dates
  df[date_cols] = df[date_cols].where(df[date_cols] <= cutoff, other=None)

  internal_date_cols = ["year_birth", "year_death"]
  df[internal_date_cols] = df[internal_date_cols].apply(
    lambda col: col.where(
      col.dropna().astype("int").reindex(col.index).le(cutoff.year), other=None
    )
  )
  return df


def write_data(df: pd.DataFrame) -> None:
  df.to_csv("./assets/results.csv", index=False)

  print("Preprocessed data and wrote to disk.")


def run(config_path: str, data_file_path: str) -> pd.DataFrame:
  config = read_config(config_path)
  col_mapping, excluded = build_column_mapping(config)
  date_cols = safe_get(config, "date_columns")
  place_cols = safe_get(config, "place_columns")
  cutoff_date = safe_get(config, "cutoff_date")

  dtypes = {x: "string" for x in col_mapping.keys()}

  df = read_data(data_file_path, col_mapping, dtypes, excluded)

  # Filter out any columns that don't exist in the data
  date_cols = [c for c in date_cols if c in df.columns]
  place_cols = [c for c in place_cols if c in df.columns]

  df = clean_data(df, date_cols)

  # TODO: Skip the normalisation and handle via SQL
  #   -> find the latest occurance of a last name
  #   -> walk down the tree from there & assign any following person the last_name_normed from the latest name
  # Normalize last names
  # name_map = generate_last_name_lookup()
  # result = apply_map(result, norm_name, name_map)

  # Load previously geocoded place map for faster data processing
  with open("assets/places_map.json", "r") as f:
    places_map = json.load(f)

  # Geocode location fields
  coder = Nominatim(user_agent="ancestry-geocoder")

  df[["place", "latitude", "longitude"]] = df.apply(
    lookup_location, args=(coder, places_map, place_cols), axis=1
  ).tolist()

  df = remove_sensitive_data(df, cutoff_date, date_cols)

  write_data(df)

  return df


if __name__ == "__main__":
  parser = ArgumentParser(description="Process data.")
  parser.add_argument(
    "-i",
    dest="data_path",
    required=True,
    help="Full path to data file.",
  )
  parser.add_argument(
    "-c",
    dest="config_path",
    required=True,
    help="Full path to config file.",
  )
  arg = parser.parse_args()

  run(arg.config_path, arg.data_path)
