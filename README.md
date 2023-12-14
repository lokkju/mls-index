# MLS Service Data Index
This project is a repository of data for MLS services.

The MLS names and ids are synchronized with the data provided by NAR at https://blog.narrpr.com/mls-map-embed/

The rest of the data is crowd-sourced and maintained by the community. Please help out by opening tickets or pull requests, with any additional data you have - especially lists of zip codes covered by each MLS.

## Data
The data is stored in individual JSON files in the `mls_data` directory.
Each file is named `{mls_name} - {mls_id}.json` and contains the following fields:
- `mls_id`: the MLS id as provied by NAR 
- `mls_name`: The MLS name as provided by NAR
-  `latitude`: The latitude of the MLS office
- `longitude`: The longitude of the MLS office
- `office_address`: The street address of the MLS office
- `office_city`: The city of the MLS office
- `office_state`: The state of the MLS office
- `office_zip`: The zip code of the MLS office 
- `phone`: The phone number of the MLS office
- `website`: The website of the MLS service
- `realtor_count_by_association`: The number of member realtors
- `associations`: A list of associations that are part of the MLS service
- `zipcode_coverage`: A list of zip codes that are covered by the MLS service

## Data Products
The above individual JSON files are combined into the following data products:
- `mls_data.jsonl`: A JSONL file containing all the data in jsonlines format
- `mls_data.gpkg`: A GeoPackage file containing all the data in GeoPackage format, with the geometry column being set to a polygon generated from the zipcodes in the zipcode coverage list
- `mls_data.png`: A PNG plot of polygons in the GeoPackage file

These data products are released as GitHub releases.

## Tooling
The Justfile contains a number of commands to help with the creating the data products:
- `just build_zcta_data`: downloads and builds Zip Code Tabulation Area (ZCTA) polygon data from the US Census Bureau
- `just build_mls_data`: builds the MLS data products from the individual JSON files
- `just release`: creates a new GitHub release with the MLS data products
