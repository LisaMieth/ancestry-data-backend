import json
import re
from pathlib import Path
from time import sleep
from datetime import datetime, date
from yaml import safe_load
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geopy.location import Location
from argparse import ArgumentParser


ROOT_DIR = Path(__file__).parent.parent


class InvalidConfigFormatError(Exception):
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message


def read_config(config_path: Path) -> dict:
  """Read provided YML config file into dictionary."""
  data = config_path.read_text()
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


def read_data(file_name: Path, mapping: dict, dtypes, excluded: list) -> pd.DataFrame:
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


def load_optional_json_map(path: Path | None) -> dict:
  """Load the optional JSON from the file path if given, otherwise return new cache"""
  if path is None:
    return {}

  try:
    return json.loads(path.read_text())
  except FileNotFoundError:
    return {}


def generate_last_name_lookup(mapping):
  """Generate name lookup from variations mapping."""
  norm_lookup = {x: key for key, vals in mapping.items() for x in vals}

  return norm_lookup


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


def geocode(geocoder: Nominatim, elem: str | None) -> Location | None:
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


def norm_last_name(row: pd.Series, mapping):
  last_name = row["last_name"]

  return mapping.get(last_name) or last_name


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


def build_relationship_dataset(df: pd.DataFrame, config: list) -> pd.DataFrame:
  return pd.concat(
    [
      df[entry["col"]]
      .rename("parent_id")
      .to_frame()
      .assign(type=entry["type"], **{"child_id": df["id"]})
      for entry in config
    ],
    ignore_index=True,
  )


def write_data(df: pd.DataFrame, file_name) -> None:
  output_path = ROOT_DIR / "output" / f"{file_name}.csv"
  output_path.parent.mkdir(parents=True, exist_ok=True)
  df.to_csv(output_path, index=False)

  print("Preprocessed data and wrote to disk.")


def run(
  input_file_path: Path,
  config_path: Path,
  places_map_path: Path | None,
  lastname_map_path: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
  config = read_config(config_path)
  col_mapping, excluded = build_column_mapping(config)
  date_cols = safe_get(config, "date_columns")
  place_cols = safe_get(config, "place_columns")
  cutoff_date = safe_get(config, "cutoff_date")
  relationship_cols = safe_get(config, "relationship_columns")

  places_map = load_optional_json_map(places_map_path)

  dtypes = {x: "string" for x in col_mapping.keys()}

  df = read_data(input_file_path, col_mapping, dtypes, excluded)

  # Filter out any columns that don't exist in the data
  date_cols = [c for c in date_cols if c in df.columns]
  place_cols = [c for c in place_cols if c in df.columns]

  df = clean_data(df, date_cols)

  # TODO: Refactor this to depend on the family branch
  # Normalize last names
  name_map = load_optional_json_map(lastname_map_path)
  name_mapping = generate_last_name_lookup(name_map)
  df["last_name_normed"] = df.apply(norm_last_name, args=(name_mapping,), axis=1)

  # Geocode location fields
  coder = Nominatim(user_agent="ancestry-geocoder")

  df[["place", "latitude", "longitude"]] = df.apply(
    lookup_location, args=(coder, places_map, place_cols), axis=1
  ).tolist()

  df = remove_sensitive_data(df, cutoff_date, date_cols)
  pd.set_option("display.max_columns", None)

  relationship_data = build_relationship_dataset(df, relationship_cols)
  person_data = df

  write_data(relationship_data, "relationships")
  write_data(person_data, "persons")

  # Save back potentially updated place map into assets folder
  places_map_path = (
    places_map_path if places_map_path else ROOT_DIR / "assets" / "places_map.json"
  )

  with open(places_map_path, "w") as f:
    json.dump(places_map, f, indent=2)

  return (person_data, relationship_data)


if __name__ == "__main__":
  parser = ArgumentParser(description="Process data.")
  parser.add_argument(
    "-i",
    dest="input_data",
    required=True,
    help="Full path to input data.",
  )
  parser.add_argument(
    "-c",
    dest="dataset_config",
    required=True,
    help="Required YAML config file.",
  )
  parser.add_argument(
    "-p",
    dest="places_map",
    required=False,
    help="Optional file for cached place name -> geolocation mapping. This cached file may be updated in place.",
  )
  parser.add_argument(
    "-n",
    dest="name_map",
    required=False,
    help="Optional file mapping last names to their normed versions.",
  )
  arg = parser.parse_args()

  run(
    Path(arg.input_data),
    Path(arg.dataset_config),
    Path(arg.places_map) if arg.places_map else None,
    Path(arg.name_map) if arg.name_map else None,
  )
