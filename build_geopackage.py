import requests
import click
import os
import re
import json
import sys
import pyjq
from datetime import datetime
from loguru import logger
import geopandas as gpd
import pandas as pd
import warnings
from tqdm import tqdm

# Register `pandas.progress_apply` and `pandas.Series.map_apply` with `tqdm`
# (can use `tqdm_gui`, `tqdm_notebook`, optional kwargs, etc.)
tqdm.pandas(desc="df.apply")

warnings.simplefilter(action='ignore', category=FutureWarning)

gpd.options.io_engine = "pyogrio"


@click.group()
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    click.echo(f"Debug mode is {'on' if debug else 'off'}")
    if not debug:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

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


@cli.command()
def update_mls_data_from_nar_blog():
    """Update MLS data from the NAR blog site"""
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


zdf = None
def zipcodes_to_covering(zipcodes: list[str]):
    global zdf
    if zdf is None:
        zdf = gpd.read_file("_data/zcta_2022_100m_preserved.gpkg")
        zdf.set_index("zip", inplace=True)

    from shapely import unary_union, MultiPolygon, concave_hull
    clean_zipcodes = [z for z in zipcodes if z in zdf.index]
    poly = zdf.loc[clean_zipcodes].geometry.values.tolist()
    poly = [p.buffer(1000) for p in poly]
    poly = unary_union(poly).buffer(-1000)

    poly = poly if poly.geom_type == 'MultiPolygon' else MultiPolygon([poly])
    poly = MultiPolygon([p for p in list(poly.geoms)])
    logger.debug(f"{len(zipcodes)} zipcodes, {len(clean_zipcodes)} cleaned zipcodes, {len(poly.geoms)} polygons")
    return poly.simplify(tolerance=500)

@cli.command()
def build_mls_data():
    """Build MLS data geopackage from the MLS data directory"""
    mls_data = []
    for filename in os.listdir("mls_data"):
        if filename.endswith(".json"):
            mls_data.append(json.load(open(os.path.join("mls_data", filename))))
    df = pd.DataFrame(mls_data)

    df['geometry'] = df['zipcode_coverage'].progress_apply(zipcodes_to_covering)
    gdf = gpd.GeoDataFrame(df, crs=3857).to_crs(4326)
    gdf.set_index("mls_id", inplace=True)
    gdf.to_file("_data/mls_data.gpkg", driver="GPKG", index=True, layer="mls_data")

if __name__ == "__main__":
    cli()
