from datetime import datetime
import unittest
from unittest.mock import Mock
from geopy.exc import GeocoderTimedOut
from src.main import (clean_date, generate_name_map, norm_name, generate_possibilities,
  geocode, generate_location_lookup, remove_sensitive_dates, remove_sensitive_person, scatter)

dformat = '%d.%m.%Y'

class TestCleanDate(unittest.TestCase):
  def test_no_values(self):
    self.assertIsNone(clean_date(None))
    self.assertIsNone(clean_date(''))
    self.assertIsNone(clean_date('?'))

  def test_inexact_same_values(self):
    """Correctly sets 01.01. as date for inexact value."""
    sample = datetime.strptime('01.01.1800', '%d.%m.%Y').date()
    self.assertEqual(clean_date('um 1800'), sample)
    self.assertEqual(clean_date('ca 1800'), sample)
    self.assertEqual(clean_date('1800'), sample)

  def test_inexact_smaller_value(self):
    """Correctly decreases year for inexact before value."""
    sample = datetime.strptime('01.01.1799', '%d.%m.%Y').date()
    self.assertEqual(clean_date('vor 1800'), sample)

  def test_inexact_larger_value(self):
    """Correctly decreases year for inexact before value."""
    sample = datetime.strptime('01.01.1801', '%d.%m.%Y').date()
    self.assertEqual(clean_date('nach 1800'), sample)


class TestNameMap(unittest.TestCase):
  def test_name_map(self):
    """Mapping should contain distinct last names with the latest available date."""
    sample = [
      {
        'date_birth': datetime.strptime('01.01.1795', dformat),
        'last_name': 'Bettinger',
      },
      {
        'date_birth': datetime.strptime('01.01.1800', dformat),
        'last_name': 'Bettinger',
      },
      {
        'date_birth': datetime.strptime('01.01.1765', dformat),
        'last_name': 'Pöttinger',
      },
    ]

    result = {
      'Bettinger': datetime.strptime('01.01.1800', dformat),
      'Pöttinger': datetime.strptime('01.01.1765', dformat),
    }

    self.assertDictEqual(generate_name_map(sample), result)


class TestNormName(unittest.TestCase):
  def setUp(self):
    self.sample_map = {
      'Bettinger': 'Bettinger',
      'Pettinger': 'Bettinger',
      'Pöttinger': 'Bettinger',
    }

  def test_norm_name_same(self):
    result = norm_name({'last_name': 'Bettinger'}, self.sample_map)
    self.assertEqual(result['last_name_normed'], 'Bettinger')

  def test_norm_name_diff(self):
    result = norm_name({'last_name': 'Pöttinger'}, self.sample_map)
    self.assertEqual(result['last_name_normed'], 'Bettinger')


class TestLocationPossibilities(unittest.TestCase):
  def test_simple_value(self):
    self.assertEqual(generate_possibilities('Griesbach'), ['Griesbach'])

  def test_inside_outside(self):
    self.assertEqual(generate_possibilities('Poigham (Karpfham)'), [
      'Poigham (Karpfham)',
      'Poigham',
      'Karpfham',
    ])


class TestGeocode(unittest.TestCase):
  def setUp(self):
    mock = Mock()
    self.mock_location = Mock()
    self.mock_location.latitude = 14.333
    self.mock_location.longitude = 14.333
    self.geocoder = mock

  def test_null_element(self):
    self.assertIsNone(geocode(self.geocoder, ''))
    self.assertIsNone(geocode(self.geocoder, None))

  def test_geocoder_is_called(self):
    self.geocoder.geocode.return_value = self.mock_location
    geocode(self.geocoder, 'München')
    self.geocoder.geocode.assert_called()

  def test_exit_on_location(self):
    """Test that function exits when location is found."""
    self.geocoder.geocode.side_effect = [None, self.mock_location]
    geocode(self.geocoder, 'Poigham (Karpfham)')
    self.assertEqual(self.geocoder.geocode.call_count, 2)

  def test_retry_on_timeout(self):
    self.geocoder.geocode.side_effect = [GeocoderTimedOut, self.mock_location]
    geocode(self.geocoder, 'Griesbach')
    self.assertEqual(self.geocoder.geocode.call_count, 2)


class TestLocationLookup(unittest.TestCase):
  def setUp(self):
    mock = Mock()
    self.mock_location = Mock()
    self.mock_location.latitude = 14.333
    self.mock_location.longitude = 14.333
    self.mock_location.address = 'Test'
    self.geocoder = mock
    self.geocoder.geocode.return_value = self.mock_location

    self.sample = [
      {'birth_place': 'Poigham (Karpfham)'},
      {'birth_place': 'Griesbach'},
      {'birth_place': 'Weng'},
    ]

  def test_generation_no_cache(self):
    fn = generate_location_lookup(self.geocoder, {})

    for elem in self.sample:
      result = fn(elem)
      self.assertEqual(result['latitude'], 14.333)
      self.assertEqual(result['longitude'], 14.333)

  def test_cache_update(self):
    cache = {
      'Reutern': {'latitude': 12.333, 'longitude': 12.333, 'address': 'Reutern'},
      'Griesbach': {'latitude': 12.333, 'longitude': 12.333, 'address': 'Griesbach'},
    }
    fn = generate_location_lookup(self.geocoder, cache=cache)

    for elem in self.sample:
      fn(elem)

    self.assertEqual(len(cache), 4)


class TestSensitiveDataRemoval(unittest.TestCase):
  def test_sensitive_people_removed(self):
    """Assert that None is returned for elements with a birthdate > 1945."""
    sample = {
      'date_birth': datetime.strptime('01.01.1980', '%d.%m.%Y').date(),
      'first_name': 'Test',
      'last_name': 'Person',
    }
    print('RESULT', remove_sensitive_person(sample))
    self.assertIsNone(remove_sensitive_person(sample))

  def test_sensitive_people_not_removed(self):
    """Assert that element is returned if birthdate < 1945."""
    sample = {
      'date_birth': datetime.strptime('01.01.1920', '%d.%m.%Y').date(),
      'first_name': 'Test',
      'last_name': 'Person',
    }

    self.assertEqual(remove_sensitive_person(sample), sample)

  def test_sensitive_dates_removed(self):
    """Assert that dates > 1945 are removed from element."""
    sample = [
      {
        'date_death': datetime.strptime('01.01.1980', '%d.%m.%Y').date(),
        'first_name': 'Test',
        'last_name': 'Person'
      },
      {
        'date_death': datetime.strptime('01.01.1920', '%d.%m.%Y').date(),
        'first_name': 'Test',
        'last_name': 'Person'
      },
    ]

    result = [
      {'date_death': None, 'first_name': 'Test', 'last_name': 'Person'},
      {
        'date_death': datetime.strptime('01.01.1920', '%d.%m.%Y').date(),
        'first_name': 'Test',
        'last_name': 'Person'
      },
    ]

    for i in range(0, 2):
      self.assertEqual(remove_sensitive_dates(sample[i]), result[i])
