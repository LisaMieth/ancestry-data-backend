import unittest
from unittest.mock import Mock
from src.preprocess import get_column_names, InvalidConfigFormatError

class PreProcessTest(unittest.TestCase):
  def test_get_column_names(self):
    config = { "columns": [{ "source_col": "ref", "target_col": "id" }]}
    result = get_column_names(config)
    self.assertEqual(result, ["id"])

  def test_raises_on_no_columns(self):
    config = { "incorrect_key": [] }
    
    with self.assertRaises(InvalidConfigFormatError):
      get_column_names(config)

  def test_raises_on_no_column_keys(self):
    config = { "columns": [{ "source_col": "ref", "target_column": "id" }] }
    
    with self.assertRaises(InvalidConfigFormatError):
      get_column_names(config)
