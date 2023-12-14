

[private]
default:
    @just --list

[private]
poetry_install:
    #!/bin/bash

    command -v poetry >/dev/null 2>&1 || { echo >&2 "I require poetry, but it's not installed.  Aborting."; exit 1; }
    poetry install

# Builds the ZCTA data
build_zcta_data: poetry_install
    #!/bin/bash
    poetry run python build_zipcode_geopkg.py

# Builds the MLS data products
build_mls_data: poetry_install
    #!/bin/bash
    MOST_RECENT_TIMESTAMP=`find ./ -type f -iname "*.py" -or -iname "*.json" -printf '%As\n' | sort -n | tail -1`
    MLS_DATA_TIMESTAMP=`stat -c %Y _data/mls_data.gpkg`
    if [ $MOST_RECENT_TIMESTAMP -gt $MLS_DATA_TIMESTAMP ]; then
      echo "MLS data is out of date; rebuilding"
      poetry run python build_geopackage.py build-mls-data
    else
      echo "MLS data is up to date"
    fi

# prints metrics about the MLS data
print_metrics:
    #!/bin/bash
    MLS_COUNT=`jq -s '.|length' mls_data/*.json`
    MLS_WITH_ZIPCODES=`jq -s '[ .[] | select( .zipcode_coverage | length > 0) ]|length' mls_data/*.json`
    MLS_WITHOUT_ZIPCODES=`jq -s '[ .[] | select( .zipcode_coverage | length == 0) ]|length' mls_data/*.json`
    TOTAL_ZIPCODES_COVERED=`jq -s '[ .[] | .zipcode_coverage[] ]|unique|length' mls_data/*.json`
    echo "- $MLS_COUNT MLS Systems"
    echo "- $MLS_WITH_ZIPCODES MLS Systems with Zip Codes"
    echo "- $MLS_WITHOUT_ZIPCODES MLS Systems without Zip Codes"
    echo "- $TOTAL_ZIPCODES_COVERED Total Zip Codes Covered"


# Builds and publishes the MLS data products
release:
    #!/bin/bash
    set -e
    trap "exit" INT

    command -v gh >/dev/null 2>&1 || { echo >&2 "I require gh, the github cli, but it's not installed.  Aborting."; exit 1; }
    command -v git >/dev/null 2>&1 || { echo >&2 "I require git, but it's not installed.  Aborting."; exit 1; }

    if [ ! -z "$(git status --porcelain)" ]; then
      echo "Working directory not clean. Please commit all changes before releasing."
      exit 1
    fi

    current_git_tag=`git name-rev --name-only --tags HEAD`
    if [ "$current_git_tag" == "undefined" ]; then
      current_git_tag="$(git --no-pager log -1 --format="%cd-%h" --date=short)-$(git rev-parse --abbrev-ref HEAD)"
      echo "Current commit not tagged; tagging as $current_git_tag"
      git tag -a "v$current_git_tag" -m "v$current_git_tag"
    fi

    just build_mls_data

    git push --tags
    gh release create "v$current_git_tag" "_data/mls_data.gpkg" "_data/mls_data.jsonl" "_data/mls_data.png" --generate-notes --verify-tag
