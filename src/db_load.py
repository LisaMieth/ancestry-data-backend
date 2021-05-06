import argparse
import os
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine

load_dotenv('.env')

# TODO: Error handling
def load_data(filename, db_url):
  # Load in the data
  df = pd.read_csv(filename)
  # Instantiate sqlachemy.create_engine object
  engine = create_engine(db_url)

  # Save the data from dataframe to
  # postgres table "ancestry_dataset"
  df.to_sql(
      'ancestry_dataset',
      engine,
      index=False, # Not copying over the index
      if_exists='replace'
  )

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--prod', dest='prod', default=False, action='store_true',
                      help='Flag if production db is supposed to be used.')

  args = parser.parse_args()

  DB_URL = os.getenv('PROD_DB_URL') if args.prod else os.getenv('DEV_DB_URL')
  input_file = 'output.csv'

  load_data(input_file, DB_URL)

  print('DONE.')
