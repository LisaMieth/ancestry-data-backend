import unittest
from unittest.mock import patch, Mock
import pandas as pd
import numpy as np
from yaml import safe_load
from datetime import datetime
from geopy.exc import GeocoderTimedOut
from src.preprocess import (
  build_column_mapping,
  InvalidConfigFormatError,
  clean_date,
  generate_possibilities,
  geocode,
  lookup_location,
  remove_sensitive_data,
  run,
)


class TestColumnMapping(unittest.TestCase):
  def test_get_column_names(self):
    config = {"columns": [{"src_col": "ref", "target_col": "id"}]}
    mapping, excluded = build_column_mapping(config)
    self.assertEqual(mapping, {"ref": "id"})
    self.assertEqual(excluded, [])

  def test_raises_on_no_columns(self):
    config = {"incorrect_key": []}

    with self.assertRaises(InvalidConfigFormatError):
      build_column_mapping(config)

  def test_raises_on_no_column_keys(self):
    config = {"columns": [{"source_col": "ref", "target_column": "id"}]}

    with self.assertRaises(InvalidConfigFormatError):
      build_column_mapping(config)


class TestCleanDate(unittest.TestCase):
  def test_no_values(self):
    self.assertIsNone(clean_date(None))
    self.assertIsNone(clean_date(""))
    self.assertIsNone(clean_date("?"))

  def test_inexact_same_values(self):
    """Correctly sets 01.01. as date for inexact value."""
    sample = datetime.strptime("01.01.1800", "%d.%m.%Y").date()
    self.assertEqual(clean_date("um 1800"), sample)
    self.assertEqual(clean_date("ca 1800"), sample)
    self.assertEqual(clean_date("1800"), sample)

  def test_inexact_smaller_value(self):
    """Correctly sets 01.01. as date for inexact before value."""
    sample = datetime.strptime("01.01.1800", "%d.%m.%Y").date()
    self.assertEqual(clean_date("vor 1800"), sample)

  def test_inexact_larger_value(self):
    """Correctly sets 01.01. as date for inexact after value."""
    sample = datetime.strptime("01.01.1800", "%d.%m.%Y").date()
    self.assertEqual(clean_date("nach 1800"), sample)

  def test_no_year_value(self):
    self.assertIsNone(clean_date("No year here"))


class TestSensitiveDataRemoval(unittest.TestCase):
  def test_sensitive_data_removal(self):
    cutoff_date = "1945-01-01"
    sample_df = pd.DataFrame(
      {
        "full_name": ["Melanie Maier", "Johannes Weber"],
        "date_birth": [
          datetime.strptime("1905-01-01".strip(), "%Y-%m-%d").date(),
          datetime.strptime("1995-01-01".strip(), "%Y-%m-%d").date(),
        ],
        "date_death": [
          datetime.strptime("1980-01-01".strip(), "%Y-%m-%d").date(),
          None,
        ],
        "year_death": ["1980", None],
        "year_birth": ["1905", "1995"],
      }
    )
    date_cols = ["date_birth", "date_death"]

    result = remove_sensitive_data(sample_df, cutoff_date, date_cols)

    # Only one row left, second row was removed as sensitive person.
    self.assertTrue(result.shape == (1, 5))

    self.assertListEqual(
      result["date_birth"].tolist(),
      [datetime.strptime("1905-01-01".strip(), "%Y-%m-%d").date()],
    )

    self.assertListEqual(
      result["date_death"].tolist(),
      [None],
    )

    self.assertListEqual(
      result["year_death"].tolist(),
      [np.nan],
    )


class TestLocationPossibilities(unittest.TestCase):
  def test_simple_value(self):
    self.assertEqual(generate_possibilities("Griesbach"), ["Griesbach"])

  def test_inside_outside(self):
    self.assertEqual(
      generate_possibilities("Poigham (Karpfham)"),
      [
        "Poigham (Karpfham)",
        "Poigham",
        "Karpfham",
      ],
    )


class TestGeocode(unittest.TestCase):
  def setUp(self):
    mock = Mock()
    self.mock_location = Mock()
    self.mock_location.latitude = 14.333
    self.mock_location.longitude = 14.333
    self.geocoder = mock

  def test_null_element(self):
    self.assertIsNone(geocode(self.geocoder, ""))
    self.assertIsNone(geocode(self.geocoder, None))

  def test_geocoder_is_called(self):
    self.geocoder.geocode.return_value = self.mock_location
    geocode(self.geocoder, "München")
    self.geocoder.geocode.assert_called()

  def test_exit_on_location(self):
    """Test that function exits when location is found."""
    self.geocoder.geocode.side_effect = [None, self.mock_location]
    geocode(self.geocoder, "Poigham (Karpfham)")
    self.assertEqual(self.geocoder.geocode.call_count, 2)

  def test_retry_on_timeout(self):
    self.geocoder.geocode.side_effect = [GeocoderTimedOut, self.mock_location]
    geocode(self.geocoder, "Griesbach")
    self.assertEqual(self.geocoder.geocode.call_count, 2)


class TestLocationLookup(unittest.TestCase):
  def setUp(self):
    mock = Mock()
    self.mock_location = Mock()
    self.mock_location.latitude = 14.333
    self.mock_location.longitude = 14.333
    self.mock_location.address = "Test"
    self.geocoder = mock
    self.geocoder.geocode.return_value = self.mock_location

  def test_generation_no_cache(self):
    data = {"birth_place": "Ingolstadt", "death_place": "Schwarzenbruck"}
    sample = pd.Series(data=data)
    cache = {}
    cols = ["birth_place", "death_place"]
    _, lat, long = lookup_location(sample, self.geocoder, cache, cols)
    self.assertEqual(lat, 14.333)
    self.assertEqual(long, 14.333)

  @patch("src.preprocess.geocode")
  def test_cache_lookup(self, geocode_mock):
    data = {"birth_place": "Ingolstadt", "death_place": "Schwarzenbruck"}
    sample = pd.Series(data=data)
    cache = {
      "Ingolstadt": {"latitude": 12.333, "longitude": 12.333, "location": "Ingolstadt"},
    }
    cols = ["birth_place", "death_place"]

    place, lat, long = lookup_location(sample, self.geocoder, cache, cols)
    self.assertEqual(lat, 12.333)
    self.assertEqual(long, 12.333)
    geocode_mock.assert_not_called()

  @patch("src.preprocess.geocode")
  def test_cache_update(self, geocode_mock):
    geocode_mock.return_value = self.mock_location
    data = {"birth_place": "Ingolstadt", "death_place": "Schwarzenbruck"}
    sample = pd.Series(data=data)
    cache = {
      "München": {"latitude": 12.333, "longitude": 12.333, "location": "München"},
    }
    cols = ["birth_place", "death_place"]

    _, _, _ = lookup_location(sample, self.geocoder, cache, cols)
    geocode_mock.assert_called_once()

    self.assertEqual(len(cache), 2)


class IntegrationTest(unittest.TestCase):
  @patch("src.preprocess.write_data")
  def test_contains_no_excluded_cols(self, write_data_mock):
    config_path = "./config/dataset_config.yaml"
    places_map_path = "./tests/resources/places_map.json"
    write_data_mock.return_value = None

    with open(config_path, "r") as f:
      data = f.read()
      config = safe_load(data)

    excluded_cols = [
      x["target_col"] for x in config["columns"] if not x.get("include", True)
    ]
    result = run(config_path, "./sample_data/SampleData.csv", places_map_path)
    intersect = list(set(excluded_cols) & set(result.columns))

    self.assertListEqual(intersect, [])
