import requests
import click
import os
import re
import json
import jsonlines
from pandarallel import pandarallel
import contextily as cx
import matplotlib.pyplot as plt

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
pandarallel.initialize(progress_bar=True)

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
def zipcodes_to_covering(zipcodes: list[str], buffer: int = 1000, tolerance: int = 500, preserver_topology: bool = True):
    global zdf
    if zdf is None:
        zdf = gpd.read_file("_data/zcta_2022_100m_preserved.gpkg")
        zdf.set_index("zip", inplace=True)

    from shapely import unary_union, MultiPolygon
    buffer_degrees = buffer / 111139
    tolerance_degrees = tolerance / 111139
    clean_zipcodes = [z for z in zipcodes if z in zdf.index]
    poly = zdf.loc[clean_zipcodes].geometry.values.tolist()
    poly = [p.buffer(buffer_degrees) for p in poly]
    poly = unary_union(poly).buffer(-buffer_degrees)

    poly = poly if poly.geom_type == 'MultiPolygon' else MultiPolygon([poly])
    poly = MultiPolygon([p for p in list(poly.geoms)])
    logger.debug(f"{len(zipcodes)} zipcodes, {len(clean_zipcodes)} cleaned zipcodes, {len(poly.geoms)} polygons")
    return poly.simplify(tolerance=tolerance_degrees, preserve_topology=preserver_topology)

@cli.command()
@click.option("-b","--buffer",help="buffer distance in meters", default=1000, show_default=True)
@click.option("-t","--tolerance",help="simplification tolerance in meters", default=500, show_default=True)
@click.option("-p","--preserve",help="preserve geometry topology",default=True, show_default=True)
def build_mls_data(buffer, tolerance, preserve):
    """Build MLS data geopackage from the MLS data directory"""
    mls_data = []
    for filename in os.listdir("mls_data"):
        if filename.endswith(".json"):
            mls_data.append(json.load(open(os.path.join("mls_data", filename))))
    with jsonlines.open("_data/mls_data.jsonl", 'w') as writer:
        writer.write_all(mls_data)
    df = pd.DataFrame(mls_data)

    df['geometry'] = df['zipcode_coverage'].parallel_apply(zipcodes_to_covering, buffer=buffer, tolerance=tolerance, preserver_topology=preserve)
    gdf = gpd.GeoDataFrame(df, crs=4326)
    gdf.set_index("mls_id", inplace=True)
    gdf.to_file("_data/mls_data.gpkg", driver="GPKG", index=True, layer="mls_data")
    ax = gdf.to_crs(3857).plot(figsize=(12, 9), cmap='nipy_spectral', alpha=0.5)
    cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik)
    plt.savefig('_data/mls_data.png', dpi=300, bbox_inches='tight', pad_inches=0.1)

if __name__ == "__main__":
    cli()
