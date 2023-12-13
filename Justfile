

default:
    @just --list

process:
    poetry run python build_geopackage.py

fetch_nar_data:
    curl https://blog.narrpr.com/mls-map-embed/

parse_nar_data_to_json_files:
    #!/bin/bash
    mkdir -p mls_data
    cat mls_data.json | jq -c -f nar-mls-transform.jqt | while read -r message; do
      mls_name=`echo $message | jq -r '.mls_name'`
      mls_name=`echo $mls_name | sed -r 's/[^[:alpha:] -]//g'`
      echo $message | jq -r '.' > "mls_data/$mls_name.json"
    done
