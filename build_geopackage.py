import requests
import shutil
import zipfile
import os
import re
import json
import pyjq
from datetime import datetime
from loguru import logger
import geopandas as gpd
from tqdm.auto import tqdm

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


def process_zipcodes():
    if not os.path.isfile(ZCTA_DATA_ZIP):
        download_file(ZCTA_DATA_URL, ZCTA_DATA_ZIP)
    if not os.path.isdir(ZCTA_DATA_DIR):
        extract_data(ZCTA_DATA_ZIP, ZCTA_DATA_DIR)
    logger.info(f"Reading {ZCTA_DATA_SHP}")
    gdf = gpd.read_file(ZCTA_DATA_SHP)

    columns = { "ZCTA5CE20": "zip", "geometry": "geometry" }
    gdf = gdf.rename(columns=columns)[columns.values()]
    for tolerence in [10, 100, 1000]:
        tolerence_degrees = tolerence / 111139
        logger.info(f"Simplifying geometry with tolerance {tolerence} meters, {tolerence_degrees} degrees...")
        gdf["geometry"] = gdf["geometry"].simplify(tolerence_degrees)
        logger.info(f"Writing to GeoPackage...")
        gdf.to_file(f"zcta_2022_{tolerence}m.gpkg", driver="GPKG")
        logger.info(f"Writing to FlatGeobuf...")
        gdf.to_file(f"zcta_2022_{tolerence}m.fgb", driver="FlatGeobuf")


def merge_nar_data_to_file(place: dict):
    json_file = f"mls_data/{re.sub(r'[^A-Za-z -]','',place['mls_name'])} - {place['mls_id']}.json"
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
            for key, value in place.items():
                if key not in data or place[key] != data[key]:
                    logger.info(f"Updating {key} with [{data.get(key)} -> {place[key]}] in {json_file}")
                    data[key] = value
    except FileNotFoundError:
        logger.info(f"Creating {json_file}")
        data = place
        data["zipcode_coverage"] = []
    except json.decoder.JSONDecodeError:
        logger.error(f"Error reading {json_file}")
        return
    json.dump(data, open(json_file, "w"), indent=2)


def update_mls_data_from_nar_blog():
    nar_url = "https://blog.narrpr.com/mls-map-embed/"
    nar_cache_path = ".nar_mls_data.html"
    nar_last_update_time = datetime.utcfromtimestamp(os.path.getmtime(nar_cache_path)) if os.path.isfile(nar_cache_path) else datetime.datetime.utcfromtimestamp(0)
    r = requests.get(nar_url, headers={
        "User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:46.0) Gecko/20100101 Firefox/46.0",
        "If-Modified-Since": nar_last_update_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    })
    if r.status_code == 304:
        logger.info("No update")
    else:
        logger.info("Update available")
        with open(nar_cache_path, "w") as f:
            f.write(r.text)
    with open(nar_cache_path, "r") as f:
        html = f.read()
        script = open("nar-mls-transform.jqt", "r").read()
        data = json.loads("{" + re.search('("places":.*}]}])', html).group(1) + "}")
        data = pyjq.all(script, data)
        logger.info(f"Found {len(data)} places")
        os.makedirs("mls_data", exist_ok=True)
        for place in data:
            merge_nar_data_to_file(place)


def zipcodes_to_covering(zipcodes: list[str]):
    zpf = gpd.read_file("zcta_2022_100m.gpkg")
    zpf.set_index("zip", inplace=True)
    zpf = zpf.loc[zipcodes]
    zpf["geometry"].cascaded_union().plot()


def build_mls_data():
    mls_data = []
    for filename in os.listdir("mls_data"):
        if filename.endswith(".json"):
            mls_data.append(json.load(open(os.path.join("mls_data", filename))))
    gdf = gpd.GeoDataFrame(mls_data)
    gdf.set_index("mls_id", inplace=True)
    print(gdf.head())


if __name__ == "__main__":
    zipcodes_to_covering(["30327", "30328", "30338", "30342", "30350"])
