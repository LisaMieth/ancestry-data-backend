import unittest
import pandas as pd
from datetime import datetime
from src.preprocess import (
  build_column_mapping,
  InvalidConfigFormatError,
  clean_date,
  remove_sensitive_data,
)


class PreProcessTest(unittest.TestCase):
  def test_get_column_names(self):
    config = {"columns": [{"src_col": "ref", "target_col": "id"}]}
    result = build_column_mapping(config)
    self.assertEqual(result, {"ref": "id"})

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
      }
    )
    date_cols = ["date_birth", "date_death"]

    result = remove_sensitive_data(sample_df, cutoff_date, date_cols)

    # Only one row left, second row was removed as sensitive person.
    self.assertTrue(result.shape == (1, 3))

    self.assertListEqual(
      result["date_birth"].tolist(),
      [datetime.strptime("1905-01-01".strip(), "%Y-%m-%d").date()],
    )

    self.assertListEqual(
      result["date_death"].tolist(),
      [None],
    )
