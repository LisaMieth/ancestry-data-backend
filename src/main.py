import csv
import difflib
import re
from os import path
from time import sleep
from datetime import datetime
from copy import deepcopy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


columns = {
	'#REFN': 'reference',
	'NAME': 'full_name',
	'FATH.NAME': 'father_name',
	'FATH.#REFN': 'father_reference',
	'MOTH.NAME': 'mother_name',
	'MOTH.#REFN': 'mother_reference',
	'_UID': 'id',
	'SURN': 'last_name',
	'GIVN': 'first_name',
	'SEX': 'gender',
	'BIRT.PLAC': 'birth_place',
	'OCCU': 'occupation',
	'SOUR': 'source',

	# Don't need those
	'CHAN.DATE': 'date_changed',
	'CHAN.DATE.TIME': 'time_changed',

	'BIRT.DATE': 'date_birth',
	'DEAT.DATE': 'date_death',
	'NOTE': 'note',
	'DEAT.PLAC': 'death_place',
	'NOTE.2': 'note_2',
	'SOUR.2': 'source_2',

	'_UID.2': 'id_2',
	'_UID.3': 'id_3',
	'OCCU.NOTE': 'occupation_note',

	'MARR.SPOU.NAME.1': 'spouse_1_name',
	'MARR.SPOU.#REFN.1': 'spouse_1_reference',
	'FAM.HUSB.1': 'husband_1_family_reference',
	'FAM.WIFE.1': 'wife_1_family_reference',
	'MARR.DATE.1': 'date_marriage_1',
	'MARR.PLAC.1': 'location_marriage_1',
	'FAM.CHIL.1': 'child_1_family_reference',
	# Don't know what this is
	'FAM.MARR.1': 'fam_marr_1',  # - some kind of boolean (Y/N/NaN)
	'FAM._STAT.1': 'family_1_status', # i.e. ('NOT MARRIED', 'None') ???
	'FAM._MARR.1': 'fam_marr_12',  # - some kind of boolean (Y/N/NaN)

	'MARR.SPOU.NAME.2': 'spouse_2_name',
	'MARR.SPOU.#REFN.2': 'spouse_2_reference',
	'FAM.HUSB.2': 'husband_2_family_reference',
	'FAM.WIFE.2': 'wife_2_family_reference',
	'MARR.DATE.2': 'date_marriage_2',
	'MARR.PLAC.2': 'location_marriage_2',
	'FAM.CHIL.2': 'child_2_family_reference',
	'FAM.MARR.2': 'fam_marr_2',  # - some kind of boolean (Y/N/NaN)
	'FAM._STAT.2': 'family_2_status', # i.e. ('NOT MARRIED', 'None') ???
	'FAM._MARR.2': 'fam_marr_22',  # - some kind of boolean (Y/N/NaN)

	'MARR.SPOU.NAME.3': 'spouse_3_name',
	'MARR.SPOU.#REFN.3': 'spouse_3_reference',
	'FAM.HUSB.3': 'husband_3_family_reference',
	'FAM.WIFE.3': 'wife_3_family_reference',
	'MARR.DATE.3': 'date_marriage_3',
	'MARR.PLAC.3': 'location_marriage_3',
	'FAM.CHIL.3': 'child_3_family_reference',
	'FAM.MARR.3': 'fam_marr_3',  # - some kind of boolean (Y/N/NaN)
	'FAM._STAT.3': 'family_3_status', # i.e. ('NOT MARRIED', 'None') ???
	'FAM._MARR.3': 'fam_marr_32',  # - some kind of boolean (Y/N/NaN)

	'MARR.SPOU.NAME.4': 'spouse_4_name',
	'MARR.SPOU.#REFN.4': 'spouse_4_reference',
	'FAM.HUSB.4': 'husband_4_family_reference',
	'FAM.WIFE.4': 'wife_4_family_reference',
	'MARR.DATE.4': 'date_marriage_4',
	'MARR.PLAC.4': 'location_marriage_4',
	'FAM.CHIL.4': 'child_4_family_reference',
	'FAM.MARR.4': 'fam_marr_4',  # - some kind of boolean (Y/N/NaN)
	'FAM._STAT.4': 'family_4_status', # i.e. ('NOT MARRIED', 'None') ???
	'FAM._MARR.4': 'fam_marr_42',  # - some kind of boolean (Y/N/NaN)

	# DON'T NEED THOSE
	'OBJE.FILE.1': 'file_1',
	'OBJE.TITL.1': 'file_1_title',
}


def read_data(file_name):
  cache = []
  f = open(path.join('data', file_name), 'r', encoding='utf-16')
  fields = list(columns.values())
  reader = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_ALL, fieldnames=fields)
  next(reader) # Skip header

  for row in reader:
    cache.append(row)

  return cache


def generate_name_map(data):
  """Create a mapping of names and most recent dates."""
  # Build last name reference list containing last name and birth/death/marriage date
  # to grab latest last name
  cache = {}

  for elem in data:
    # Get a possible date from this person
    date = elem.get('date_birth', elem.get('date_death', elem.get('date_marriage_1', None)))
    name = elem.get('last_name', None)
    value = cache.get(name, None)

    if date is None or date == '':
      continue

    if not value:
      cache[name] = date

    else:
      # Add the newer date
      if date and date > value:
        cache[name] = date

  return cache


def name_lookup(elem, possibilities):
  """Returns the closest matches to the element"""
  return difflib.get_close_matches(elem, possibilities, n=10, cutoff=0.8)


def norm_name(elem, mapping):
  """Grab the latest version of a name."""
  cache = deepcopy(elem)
  possibilities = name_lookup(elem['last_name'], mapping.keys())
  dates = [mapping[x] for x in possibilities]
  sorted_names = [x for _,x in sorted(zip(dates, possibilities))]
  normed = sorted_names[-1] if len(sorted_names) > 0 else elem['last_name']
  cache['last_name_normed'] = normed

  return cache


def clean_date(value):
  """Cast date strings to formatted datetime values for comparison"""
  if not value or value == '' or value == '?':
    return None

  # Replace inexact values with something more precise
  if 'um' in value:
    value = value.replace('um ', '01.01.')

  if 'vor' in value:
    value = value.replace('vor ', '')
    value = f'01.01.{int(value) - 1}'

  if 'nach' in value:
    value = value.replace('nach ', '')
    value = f'01.01.{int(value) + 1}'

  if '.' not in value:
    value = f'01.01.{value}'

  value_match = re.search(r'\d{2}.\d{2}.\d{4}', value)

  if value_match:
    value = value_match.group()

  return datetime.strptime(value.strip(), '%d.%m.%Y')


def clean_data(elem):
  # Shallow copy is enoug?
  cache = elem.copy()

  # Clean date values
  for d in [
    'date_birth',
    'date_death',
    'date_marriage_1',
    'date_marriage_2',
    'date_marriage_3',
    'date_marriage_4',
  ]:
    date = elem.get(d, None)

    if date:
      cache[d] = clean_date(date)

  # Clean last name values
  cache['last_name'] = re.sub(r'\(|\)|\?', '', elem['last_name'])

  return cache


def coalesce(*values):
  for item in values:
    if item is not None and item != '':
      return item

  return None


def geocode(geocoder, elem):
  if elem == '' or elem is None:
    return None

  # Lookup entire location as well as possible separated values i.e.
  # elem before () and inside ()
  possibilities = [elem]
  location = None

  if '(' in elem:
    outside = re.findall(r"(.*?)\(.*\)+", elem)
    inside = re.findall(r'\((.*?)\)', elem)
    possibilities.append(outside[0].strip())
    possibilities.append(inside[0].strip())

  for item in possibilities:
    if location:
      break

    try:
      location = geocoder.geocode(f'{item}, Germany', language='DE')
    except GeocoderTimedOut:
      sleep(5)
      # Add for retry
      possibilities.append(item)

  return location


def generate_location_lookup():
  """Grab the geocode of the first non-null place element of the given record and add it
  to the record and cache"""
  cache = {}
  coder = Nominatim(timeout=20, user_agent='ancestry-geocoder')
  place_columns = [
    'birth_place',
    'death_place',
    'location_marriage_1',
    'location_marriage_2',
    'location_marriage_3',
    'location_marriage_4',
  ]

  def lookup(elem):
    place = coalesce(*[elem.get(x) for x in place_columns])
    location = cache.get(place, None)

    if location is None:
      location = geocode(coder, place)
      cache[place] = location

    elem['latitude'] = location.latitude if location else None
    elem['longitude'] = location.longitude if location else None

    return elem

  return lookup


def apply_fn(l, func, *args):
  return [func(x, *args) for x in l]


def write_data(data):
  f = open('output.csv', 'w')
  fields = list(columns.values())
  fields.extend(['last_name_normed', 'latitude', 'longitude'])

  with f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for row in data:
      writer.writerow(row)

  f.close()
  print('Finished')


if __name__ == '__main__':
  input_data = read_data('Combined-All-10-2020.csv')
  cleaned = apply_fn(input_data, clean_data)
  name_map = generate_name_map(cleaned)
  result = apply_fn(cleaned, norm_name, name_map)
  lookup_fn = generate_location_lookup()
  geocoded = apply_fn(result, lookup_fn)

	write_data(geocoded)
