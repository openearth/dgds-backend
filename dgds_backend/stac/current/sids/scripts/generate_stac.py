import pystac
import os
import pathlib
from pystac import Catalog, CatalogType, Collection, Summaries

from stac.blueprint import (
    IO,
    Layout,
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_template_collection,
)
from stac.datacube import add_datacube
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
    rm_special_characters,
)

if __name__ == "__main__":

    TYPE = "Feature"
    ON_CLICK = {}
    VARIABLES = ["sids"]  # xarray variables in dataset
    MAPBOX_PROJ = "global-data-viewer"
    DATASET_FILENAME = "BOX_130_029_QAed-4qqvm5"

    # STAC configs
    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_TITLE = "Small island development states"
    COLLECTION_ID = "ssl"  # name of stac collection
    DATASET_DESCRIPTION = """description"""

    # functions to generate properties that vary per dataset but cannot be hard-corded because
    # they also require input arguments
    def get_paint_props(item_key: str):
        return {
            "circle-color": [
                "interpolate",
                ["linear"],
                ["get", item_key],
                0,
                "hsl(110,90%,80%)",
                1.5,
                "hsla(55, 88%, 53%, 0.5)",
                3.0,
                "hsl(0, 90%, 70%)",
            ],
            "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                0,
                0.5,
                1,
                1,
                5,
                5,
            ],
        }

    def get_mapbox_url(
        mapbox_proj: str, filename: str, var: str, add_mapbox_protocol=True
    ) -> str:
        """Generate tileset name"""

        tilename = f"{pathlib.Path(filename).stem}_{var}"
        if len(tilename) > 32:
            raise ValueError("Mapbox tilenames cannot be longer than 32 characters.")

        # for uploading geojson to mapbox the mapbox protocol should not be included
        if not add_mapbox_protocol:
            return f"{mapbox_proj}.{tilename}"

        return f"mapbox://{mapbox_proj}.{tilename}"

    template_fp = os.path.join(
        './', STAC_DIR, TEMPLATE_COLLECTION, "collection.json"
    )

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=COLLECTION_TITLE,
        description=DATASET_DESCRIPTION,
    )

    # generate stac feature keys (strings which will be stac item ids) for mapbox layers
    # dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
    # dimcombs = get_dimension_dot_product(dimvals)

    # TODO: check what can be customized in the layout
    layout = Layout()

    for var in VARIABLES:

        # add zarr store as asset to stac_obj
        #collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

        # stac items are generated per AdditionalDimension (non spatial)
        #for dimcomb in dimcombs:

        mapbox_url = get_mapbox_url(MAPBOX_PROJ, DATASET_FILENAME, var)

        # generate stac item key and add link to asset to the stac item
        #item_id = get_mapbox_item_id(dimcomb)
        feature = gen_default_item(f"{var}-mapbox-{item_id}")
        feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

        # This calls ItemCoclicoExtension and links CoclicoExtension to the stac item
        # coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

        # coclico_ext.item_key = item_id
        # coclico_ext.paint = get_paint_props(item_id)
        # coclico_ext.type_ = TYPE
        # coclico_ext.on_click = ON_CLICK

        # TODO: include this in our datacube?
        # add dimension key-value pairs to stac item properties dict
        # for k, v in dimcomb.items():
        #     feature.properties[k] = v

        # # add stac item to collection
        collection.add_item(feature, strategy=layout)

    print(collection)