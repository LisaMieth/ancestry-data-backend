import unittest
from datetime import datetime
from unittest.mock import Mock
from src.preprocess import build_column_mapping, InvalidConfigFormatError


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
