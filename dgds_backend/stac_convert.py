"""
This file converts the old catalog(s) into a STAC compatible
collection underneath stac/current

Note that we hardcode the url for the static collection,
it thus needs to be set here on top.

At the end we "break" this collection on disk,
as the links to the GEE collections point to the API
and not to the files next to it.

We leave these orphans on disk, so we can load them
as templates for serving them dynamically.

At the moment it's difficult to save partial STAC collections
with pystac without crawling all links/childs.
"""


import json
import shutil
from datetime import datetime
from pathlib import Path

import pystac
import requests
from pystac import CatalogType, Collection

# server = "http://localhost:5000"  # for local development
server = "https://blueearthdata.org/api"

APP_DIR = Path(__file__).parent

# Dataset settings
DATASETS = {}
fnameDatasets = Path(APP_DIR / "config_data" / "datasets.json")
fnameAccess = Path(APP_DIR / "config_data" / "datasets_access.json")
with open(str(fnameDatasets), "r") as fd:
    DATASETS["info"] = json.load(fd)  # str for python 3.4, works without on 3.6+
with open(str(fnameAccess), "r") as fa:
    DATASETS["access"] = json.load(fa)  # str for python 3.4, works without on 3.6+
lookup_themes = {item["id"]: item["name"] for item in DATASETS["info"]["themes"]}

# Root
world_bbox = [-180, -90, 180, 90]
world = pystac.SpatialExtent(world_bbox)
world_poly = {
    "type": "Polygon",
    "coordinates": [
        [
            [-180.0, -90.0],
            [180.0, -90.0],
            [180.0, 90.0],
            [-180.0, 90.0],
            [-180.0, -90.0],
        ]
    ],
}
capture_date = datetime.strptime("2015-10-22", "%Y-%m-%d")
tmp_extent = pystac.TemporalExtent([(capture_date, None)])
extent = pystac.Extent(world, tmp_extent)


def layeroptionstobands(layeroptions):
    return [
        {"name": item["band"], "description": item["name"]} for item in layeroptions
    ]


asset = pystac.Asset(
    title="Deltares Public Wiki",
    href="https://publicwiki.deltares.nl/display/BED/References",
    description="Deltares Public Wiki about Blue Earth Data",
    media_type="application/html",
    roles=["metadata"],
)
deltares = Collection(
    id="deltares-blueearthdata",
    description="Deltares BlueEarth Data Collection",
    extent=extent,
    license="various",
    extra_fields={
        "assets": {"metadata": asset.to_dict()},
        "summaries": {"keywords": list(lookup_themes.values())},
    },
)
provider = pystac.Provider(
    name="Deltares",
    description="Deltares is an independent institute for applied research in the field of water and subsurface.",
    roles=["producer", "processor"],
    url="https://www.deltares.nl",
)

for dataset in DATASETS["info"]["datasets"]:
    bbox = pystac.SpatialExtent(dataset["bbox"][0] + dataset["bbox"][1])
    extent = pystac.Extent(bbox, tmp_extent)
    themes = [lookup_themes[theme] for theme in dataset["themes"]]
    collection = pystac.Collection(
        id=dataset["id"],
        title=dataset["name"],
        description=dataset["toolTip"],
        extent=extent,
        keywords=themes,
        providers=[provider],
        properties={
            "deltares:scope": dataset["scope"],
            "deltares:timeSpan": dataset["timeSpan"],
            "deltares:units": dataset["units"],
        },
    )

    # GEE layers with rasters
    rasterdata = DATASETS["access"][dataset["id"]]["rasterService"]
    timedata = DATASETS["access"][dataset["id"]]["dataService"]

    if rasterdata["url"] != "":

        if "layerOptions" in dataset:
            bands = {
                "summaries": {"eo:bands": layeroptionstobands(dataset["layerOptions"])}
            }
        else:
            bands = {}

        assets = {}
        fasset = pystac.Asset(
            title="FeatureInfo",
            href=rasterdata["featureinfo_url"],
            properties={"name": rasterdata["name"]},
            description="FeatureInfo",
            media_type="application/json",
            roles=["featureinfo"],
        )
        assets["featureinfo"] = fasset.to_dict()

        extra = {"assets": assets}
        extra.update(bands)

        rastersubcollection = pystac.Collection(
            id=collection.id + "-gee",
            title=collection.title,
            description=collection.description,
            extent=collection.extent,
            keywords=collection.keywords,
            providers=[provider],
            extra_fields=extra,
            properties={
                "deltares:name": rasterdata["name"],
                "deltares:parameters": rasterdata["parameters"],
                "deltares:url": rasterdata["url"],
            },
        )

        post_data = {"dataset": rasterdata["name"], "imageId": None}
        post_data.update(rasterdata["parameters"])
        resp = requests.post(url=rasterdata["url"], json=post_data)
        if resp.status_code == 200:
            data = resp.json()
            timeseries = (
                data.pop("imageTimeseries") if "imageTimeseries" in data else []
            )
            url = data.pop("url")
            if data["imageId"] is None:
                imageId = data["dataset"]
            else:
                imageId = data["imageId"].split("/")[-1]

            if "date" in data and data["date"] is not None:
                date = datetime.strptime(data["date"], "%Y-%m-%dT%H:%M:%S")
            else:
                date = datetime.now()
            # print(collection.id, imageId)
            item = pystac.Item(
                id=collection.id + "-gee-" + imageId,
                properties={"deltares:" + key: value for (key, value) in data.items()},
                geometry=world_poly,
                bbox=world_bbox,
                datetime=date,
            )
            item.add_asset(
                "visual",
                pystac.Asset(
                    title="GEE",
                    href=url,
                    description="GEE WMS url",
                    media_type="application/png",
                    roles=["visual"],
                    properties={
                        "eo:bands": layeroptionstobands(dataset["layerOptions"])
                    }
                    if "layerOptions" in dataset
                    else {},
                ),
            ),
            item.add_asset(
                "data",
                pystac.Asset(
                    title="COG",
                    href="gs://?",
                    description="Google Bucket COG",
                    media_type="application/geotiff",
                    roles=["data"],
                ),
            ),
            rastersubcollection.add_item(item, title=item.id)

        collection.add_child(rastersubcollection, title=rastersubcollection.id)

    if "flowmapLayer" in dataset.keys():
        flow = dataset["flowmapLayer"]
        data = collection.to_dict()

        asset = pystac.Asset(
            title="flowmap",
            href="https://storage.googleapis.com/dgds-data/flowmap_glossis/tiles/glossis-current-202003300600/{z}/{x}/{y}.png",
            description="Deltares Public Wiki about Blue Earth Data",
            media_type="application/html",
            roles=["flowmap"],
        )

        flowsubcollection = pystac.Collection(
            id=collection.id + "-flow",
            title=collection.title,
            description=collection.description,
            extent=collection.extent,
            keywords=collection.keywords,
            providers=[provider],
            extra_fields={"assets": {"flowmap": asset.to_dict()}},
            properties={
                "deltares:min": -0.5,
                "deltares:max": 0.5,
                "deltares:nParticles": 10000,
                "deltares:minZoom": 0,
                "deltares:maxZoom": 5,
            },
        )

        collection.add_child(flowsubcollection, title=flowsubcollection.id)

    if "vectorLayer" in dataset.keys():
        layers = dataset["vectorLayer"]["mapboxLayers"]

        assets = {}
        asset = pystac.Asset(
            title="Timeseries",
            href="https://blueearthdata.org/api/timeseries",
            description="Timeseries endpoint",
            media_type="application/json",
            roles=["graph"],
        )
        assets["graph"] = asset.to_dict()

        tasset = pystac.Asset(
            title=timedata["name"],
            href=timedata["url"],
            properties={"name": timedata["name"]},
            description="TimeSeries",
            media_type=timedata["protocol"],
            roles=["timeseries"],
        )
        assets["timeseries"] = tasset.to_dict()

        extra = {"assets": assets}

        vecsubcollection = pystac.Collection(
            id=collection.id + "-mapbox",
            title=collection.title,
            description=collection.description,
            extent=collection.extent,
            keywords=collection.keywords,
            providers=[provider],
            extra_fields=extra,
            properties={
                "deltares:locationIdField": dataset["locationIdField"],
                "deltares:units": dataset["units"],
                "deltares:pointData": dataset["pointData"],
            },
        )
        for layer in layers:
            item = pystac.Item(
                id=vecsubcollection.id + "-" + layer["id"].lower(),
                properties={"deltares:" + key: value for (key, value) in layer.items()},
                geometry=world_poly,
                bbox=world_bbox,
                datetime=datetime.now(),
            )
            item.add_asset(
                "mapbox",
                pystac.Asset(
                    title="Mapbox",
                    href=layer["source"]["url"],
                    description="Mapbox url",
                    media_type=layer["source"]["type"],
                    roles=["mapbox"],
                ),
            ),
            vecsubcollection.add_item(item, title=item.id)
        collection.add_child(vecsubcollection, title=vecsubcollection.id)

    deltares.add_child(collection, title=collection.id)


# End, save everything
deltares.describe()
# deltares.normalize_hrefs(
#     "https://raw.githubusercontent.com/openearth/blueearthdata/main/current"
# )
url = f"{server}/static_stac/"
deltares.normalize_hrefs(url)

deltares.validate_all()
deltares.save(catalog_type=CatalogType.ABSOLUTE_PUBLISHED)


shutil.rmtree("stac/current", ignore_errors=True)
serverfolder = server.replace("//", "/")
shutil.move(f"{serverfolder}/static_stac/", "dgds_backend/stac/current")
shutil.rmtree(serverfolder.split("/")[0], ignore_errors=True)


# Replace static links with dynamic ones
# http://localhost:5000/static_stac/cc/cc-gee/collection.json
# becomes
# http://localhost:5000/stac/cc-gee
stacdir = Path(__file__).parent / "stac/current"
for fn in stacdir.resolve().glob("**/*"):
    if fn.is_file() and fn.name == "collection.json":
        # Override Pystac loading, as it resets self links etc.
        coll = json.loads(open(fn).read())
        write = False
        id = coll["id"]
        for link in coll["links"]:
            if "static_stac" in link["href"] and "-gee/collection.json" in link["href"]:
                link["href"] = f"{server}/stac/{id}-gee"
                write = True
        if write:
            data = json.dumps(coll, indent=4)
            with open(fn, "w") as f:
                f.write(data)
