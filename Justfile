

default:
    @just --list

poetry_install:
    #!/bin/bash

    command -v poetry >/dev/null 2>&1 || { echo >&2 "I require poetry, but it's not installed.  Aborting."; exit 1; }
    poetry install

build_zcta_data: poetry_install
    #!/bin/bash
    poetry run python build_zipcode_geopkg.py

build_mls_data: poetry_install
    #!/bin/bash
    poetry run python build_geopackage.py build-mls-data

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

    [ -f "_data/mls_data-$current_git_tag.gpkg" ] || just build_mls_data && \
     mv _data/mls_data.gpkg "_data/mls_data-$current_git_tag.gpkg" && \
     mv _data/mls_data.jsonl "_data/mls_data-$current_git_tag.jsonl"

    git push --tags
    gh release create "v$current_git_tag" "_data/mls_data-$current_git_tag.gpkg" "_data/mls_data-$current_git_tag.jsonl" --generate-notes --verify-tag
