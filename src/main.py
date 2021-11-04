import csv
import re
import json
from os import path
from time import sleep
from datetime import datetime
from argparse import ArgumentParser
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
	# '_UID.3': 'id_3',
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

# TODO: Figure out how to handle duplicate family names in family tree lookup
# example 'Lindtmayr' (Anna, verheiratet mit Funk Jakob)
#  & Lindtmayr Maria (verheiratet mit Straiffer Sebastian)
# This is currently the only approach that works across the board. Any prerpocessing or phonetic
# comparison is either too loose or too restrictive for the different values that need to 
# potentially match.
variations_mapping = {
  'Amann': ['Aemann', 'Amon'],
  'Bettinger': ['Pettinger', 'Pöttinger'],
  'Böttichhofer': ['Betzighofer', 'Bettighofer'],
  'Böller': ['Beller'],
  'Claß': ['Clas'],
  'Diez': ['Dirz'],
  'Dreischl': ['Droschl'],
  'Eckart': ['Eckhard'],
  'Eckmüller': ['Edmüller'],
  'Eibl': ['Älbl'],
  'Feigl': ['Faigl'],
  'Forster': ['Vorster'],
  'Funk': ['Funck'],
  'Gänther': ['Gänthner'],
  'Grabmaier': ['Grabmayr', 'Grabmair'],
  'Grahammer': ['Krahammer', 'Krahamer'],
  'Greil': ['Kreil', 'Kraell', 'Kroell'],
  'Hofertseder': ['Hofferseder', 'Hoffereder'],
  'Kinader': ['Khenater', 'Khenader', 'Kenater'],
  'Kollmann': ['Kohlmann'],
  'Kriechbaumer': ['Kriechbauer'],
  'Lämpl': ['Lampl'],
  'Leyrer': ['Leirer', 'Leurer'],
  'Lindtmayr': ['Lindemayr'],
  'Metzger': ['Mezger'],
  'Moßmiller': ['Moosmüller'],
  'Nasl': ['Näßl', 'Nesl'],
  'Neugschwender': ['Neuschwender', 'Neuschwendner'],
  'Neumair': ['Neumayr'],
  'Perstorfer': ['Peherstorfer'],
  'Pföterl': ['Pfötterl'],
  'Rottenfußer': ['Rotnfußer'],
  'Ruedorfer': ['Ruedorffer', 'Ruhdorfer'],
  'Rummelsberger': ['Rumelsberger'],
  'Spöckmair': ['Spöckmayr'],
  'Zächerl': ['Zacherl'],
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
  """Creates a mapping of names and most recent dates."""
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


def generate_last_name_lookup():
  """Generate name lookup from variations mapping."""
  norm_lookup = {x: key for key, vals in variations_mapping.items() for x in vals}
  norm_lookup.update({key: key for key in variations_mapping})

  return norm_lookup


def norm_name(elem, mapping):
  """Grab the normalised version of a given last name if it differs from original."""
  cache = elem.copy()
  last_name = cache['last_name']
  cache['last_name_normed'] = mapping.get(last_name) or last_name

  return cache


def add_variations(elem, mapping):
  """Add potential last name variations."""
  cache = elem.copy()
  cache['last_name_variations'] = mapping.get(cache['last_name_normed']) or None

  return cache


def clean_date(value):
  """Casts date strings to formatted datetime values for comparison."""
  if not value or value == '' or value == '?':
    return None

  # Replace inexact values with something more precise
  if 'um' in value:
    value = value.replace('um ', '01.01.')

  if 'ca' in value:
    value = value.replace('ca ', '01.01.')

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
  """Cleans date and last_name fields."""
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


def generate_possibilities(value):
  """Returns list of possible location values from given input value."""
  possibilities = [value]

  # A value can contain a broader parent location - Poigham (Karpfham)
  if '(' in value:
    outside = re.findall(r"(.*?)\(.*\)+", value)
    inside = re.findall(r'\((.*?)\)', value)

    possibilities.append(outside[0].strip())
    possibilities.append(inside[0].strip())

  return possibilities


def geocode(geocoder, elem):
  """Attempts to find geocode for the given value or its possibilities."""
  if elem == '' or elem is None:
    return None

  # Lookup entire location as well as possible separated values i.e.
  # elem before () and inside ()
  possibilities = generate_possibilities(elem)
  location = None

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


def generate_location_lookup(geocoder, cache=None):
  """Creates a geocode lookup function."""
  place_columns = [
    'birth_place',
    'death_place',
    'location_marriage_1',
    'location_marriage_2',
    'location_marriage_3',
    'location_marriage_4',
  ]

  if cache is None:
    cache = {}

  def lookup(elem):
    """Grabs the geocode of the first non-null place element of the given record and adds it
    to the record and cache."""
    place = coalesce(*[elem.get(x) for x in place_columns])
    location = cache.get(place, None)
    latitude, longitude = None, None

    if location:
      latitude = location['latitude']
      longitude = location['longitude']

    else:
      location = geocode(geocoder, place)

      if location:
        latitude = location.latitude
        longitude = location.longitude
        cache[place] = {'latitude': latitude, 'longitude': longitude, 'location': location.address}

    elem['latitude'] = latitude
    elem['longitude'] = longitude

    return elem

  return lookup


def remove_sensitive_person(elem):
  """Filters out any person born after 1945."""
  date_value = elem.get('date_birth', None)

  if date_value and date_value > datetime.strptime('01.01.1945', '%d.%m.%Y'):
    return None

  return elem


def remove_sensitive_dates(elem):
  """Removes any date that is > 1945."""
  cache = elem.copy()

  for item in [
    'date_birth',
    'date_death',
    'date_marriage_1',
    'date_marriage_2',
    'date_marriage_3',
    'date_marriage_4',
  ]:
    value = elem.get(item, None)
    if value and value > datetime.strptime('01.01.1945', '%d.%m.%Y'):
      cache[item] = None

  return cache


def apply_map(l, func, *args):
  """Maps over list by applying given function with any passed arguments"""
  return [func(x, *args) for x in l]


def apply_filter(l, func):
  return list(filter(func, l))


def write_data(data):
  filename = 'output.csv'
  f = open(filename, 'w')
  fields = list(columns.values())
  fields.extend(['last_name_normed', 'last_name_variations', 'latitude', 'longitude'])

  with f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for row in data:
      writer.writerow(row)

  f.close()
  print(f'Processed data and dumped it to {filename}')


def run(input_file):
  input_data = read_data(input_file)

  # Clean date & name fields
  result = apply_map(input_data, clean_data)

  # Normalize last names
  name_map = generate_last_name_lookup()
  result = apply_map(result, norm_name, name_map)

  # Add last name variations
  result = apply_map(result, add_variations, variations_mapping)

  # Load previously geocoded place map for faster data processing
  places_map = json.load(open('./places_map.json', 'r'))

  # Geocode location fields
  coder = Nominatim(timeout=20, user_agent='ancestry-geocoder')
  lookup_fn = generate_location_lookup(coder, places_map)
  result = apply_map(result, lookup_fn)

  # Remove sensitive data
  result = apply_map(result, remove_sensitive_dates)
  result = apply_filter(result, remove_sensitive_person)

  # Save back potentially updated place map
  json.dump(places_map, open('./places_map.json', 'w'), indent=2)

  write_data(result)


if __name__ == '__main__':
  parser = ArgumentParser(description='Process data.')
  parser.add_argument(
    '-i',
    dest='input_file',
    required=True,
    help='Input file located in `data` directory.'
  )
  arg = parser.parse_args()

  run(arg.input_file)
