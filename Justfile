

default:
    @just --list

build_mls_data:
    poetry run python build_geopackage.py build-mls-data

release:
    #!/bin/bash

