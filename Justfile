

default:
    @just --list

build_mls_data:
    poetry run python build_geopackage.py build-mls-data

release:
    #!/bin/bash
    if [ ! -z "$(git status --porcelain)" ]; then
      echo "Working directory not clean. Please commit all changes before releasing."
      exit 1
    fi

    current_git_tag=`git name-rev --name-only --tags HEAD`
    if [ "$current_git_tag" == "undefined" ]; then
      current_git_tag="$(git --no-pager log -1 --format="%cd_%h" --date=short)"
      echo "Current commit not tagged; tagging as $current_git_tag"
      git tag -a "v$current_git_tag" -m "v$current_git_tag"
    fi

    [ -f "_data/mls_data-$current_git_tag.gpkg" ] || just build_mls_data && mv _data/mls_data.gpkg "_data/mls_data-$current_git_tag.gpkg"

