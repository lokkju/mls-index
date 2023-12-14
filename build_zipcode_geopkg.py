import requests
import shutil
import zipfile
import os
from loguru import logger
import geopandas as gpd
from tqdm.auto import tqdm
import click

tqdm.pandas(desc="df.apply")

gpd.options.io_engine = "pyogrio"


ZCTA_DATA_URL = "https://www2.census.gov/geo/tiger/TIGER2022/ZCTA520/tl_2022_us_zcta520.zip"
ZCTA_DATA_BASENAME = os.path.splitext(os.path.basename(ZCTA_DATA_URL))[0]
ZCTA_DATA_ZIP = os.path.join("_data",os.path.basename(ZCTA_DATA_URL))
ZCTA_DATA_DIR = os.path.join("_data", ZCTA_DATA_BASENAME)
ZCTA_DATA_SHP = os.path.join(ZCTA_DATA_DIR, f"{ZCTA_DATA_BASENAME}.shp")


def download_file(src_uri: str, dest_file: str = None):
    if dest_file is None:
        dest_file = os.path.basename(src_uri)
    logger.info(f"Downloading {src_uri} to {dest_file}")
    with requests.get(src_uri, stream=True) as r:
        total_length = int(r.headers.get("Content-Length"))
        with tqdm.wrapattr(r.raw, "read", total=total_length, desc="") as raw:
            with open(dest_file, 'wb') as output:
                shutil.copyfileobj(raw, output)


def extract_data(src_file: str, dest_dir: str):
    logger.info(f"Extracting {src_file} to {dest_dir}")
    with zipfile.ZipFile(src_file, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)


@click.command()
@click.option("-t","--tolerence",help="simplification tolerance in meters", default=100, show_default=True)
@click.option("-p","--preserve",help="preserve geometry topology",default=True, show_default=True)
def create_geopkg(tolerence: str,preserve: bool):
    if not os.path.isfile(ZCTA_DATA_ZIP):
        download_file(ZCTA_DATA_URL, ZCTA_DATA_ZIP)
    if not os.path.isdir(ZCTA_DATA_DIR):
        extract_data(ZCTA_DATA_ZIP, ZCTA_DATA_DIR)
    logger.info(f"Reading {ZCTA_DATA_SHP}")
    gdf = gpd.read_file(ZCTA_DATA_SHP)

    columns = { "ZCTA5CE20": "zip", "geometry": "geometry" }
    gdf = gdf.rename(columns=columns)[columns.values()]
    tolerence_degrees = tolerence / 111139
    logger.info(f"Simplifying geometry with tolerance {tolerence} meters, {tolerence_degrees} degrees...")
    gdf["geometry"] = gdf["geometry"].simplify(tolerence_degrees, preserve)
    fn = f'_data/zcta_2022_{tolerence}m_{"preserved" if preserve else ""}.gpkg'
    logger.info(f"Writing to GeoPackage at {fn}...")
    gdf.to_file(fn, driver="GPKG",layer="zcta")

if __name__ == "__main__":
    create_geopkg()