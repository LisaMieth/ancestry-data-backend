# Ahnenforschung - Ancestry

> Creating space for my ancestors

## About
This small project processes CSV based ancestry data and loads it into a PostgresSQL DB.


It is intended for personal use only.


## Where is this data coming from?
The data is manually collected and managed by myself in the open source ancestry software Ahnenblatt.
It is coming from some online sources (like ancestry.com, myheritage.com, genealogie-kiening.de) but the vast majority is collected from church records that are either publicly accessible (via Matricula) or from the archives.
For online sourced data (including Matricula), links are provided. However, due to constant updating of these sources on the provider's end, some links may break.

The data by its nature is incomplete and can be faulty (especially in earlier centuries when it comes to identifying parents of ancestors).

## Technical Process
The data is manually exported from its source software (Ahnenblatt) as CSV and processed via Python.
Due to the size, local processing is absolutely sufficient.
Since it is manually entered data (although extensively cleaned), some specific processing steps are necessary.

*Processing steps*
- cleaning of last names
  - women where the last name is unknown are referred to with their husband's last name in `()`. 
- cleaning of dates
  - due to uncertainty around dates of births/marriages/deaths, sometimes only a year or an approximation is given (like before 1755 or after 1822); these are always replaced with the `01.01.{year}` for parsability
- normalize last names
  - last names were subjected to change over time due to individual writing & pronounciation
  - as far as possible & useful, the original spelling found in church records has been kept
  - to identify members of a family by last name easily, the last name is normalized by looking up close matches (`difflib`) and grabbing the latest version
- geocoding
  - for plotting this data on a map, geocoding is essential
  - locations are coalesced before geocoding (since some persons may only be known for one of birth/marriage/death location)
  - some locations are very small villages, specifying the next larger village/town manually was necessary in the source data to find a correct match
  - in some cases, only the next larger village is geocodable 
  - geocoding is the most time consuming step in this process, for ease of use, the geocodes are persisted and dumped to disk for reuse
- removing sensitive data including any person born after 1945 & removing any dates after 1945