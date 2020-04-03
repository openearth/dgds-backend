# -*- coding: utf-8 -*-

import argparse
import logging
from os import makedirs
from os.path import exists
from shutil import rmtree

from utils import fm_to_tiff, list_blobs, upload_to_gee, wait_gee_tasks, upload_dir_to_bucket
from waterlevel import create_water_level_astronomical_band
from waveheight import glossis_waveheight_to_tiff
from wind import glossis_wind_to_tiff

# this file is in  camelCase notation for compatibility with .js code, rename to this naming convention
from glossis2flowmap import exportFlowmap as export_flowmap
from glossis2flowmap import generateWgs84Tiles as generate_wgs84_tiles

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Setup CMD
    parser = argparse.ArgumentParser(
        description="Parse GLOSSIS netcdf output and upload to GEE."
    )
    parser.add_argument("bucket", type=str, nargs=1, help="Google bucket")
    parser.add_argument(
        "prefix", type=str, nargs=1, help="Input folder/prefix", default="fews_glossis/"
    )
    parser.add_argument("assetfolder", type=str, nargs=1, help="GEE asset")

    args = parser.parse_args()
    logging.info(args.bucket)

    bucket = args.bucket[0]
    public_bucket = args.bucket[0] + '-public'
    prefix = args.prefix[0]

    # Setup directory
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    # clear items in gee folder in bucket
    old_blobs = list_blobs(bucket, "gee")
    for blob in old_blobs:
        blob.delete()
        logging.info(f"Blob {blob} deleted.")

    taskids = []

    waterlevel_tiff_filenames = fm_to_tiff(
        bucket,
        args.prefix[0],
        tmpdir,
        variables=["water_level_surge", "water_level"],
        filter="waterlevel",
        output_fn="glossis_waterlevel",
        nodata=-9999,
        extra_bands=1,  # for astronomical tide
    )

    # Update third band in rasters
    for waterlevel_tiff_filename in waterlevel_tiff_filenames:
        create_water_level_astronomical_band(waterlevel_tiff_filename)

    for file in waterlevel_tiff_filenames:
        taskid = upload_to_gee(
            file,
            bucket,
            args.assetfolder[0] + "/waterlevel/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    current_tiff_filenames = fm_to_tiff(
        bucket,
        args.prefix[0],
        tmpdir,
        variables=["currents_u", "currents_v"],
        filter="currents",
        output_fn="glossis_currents",
        nodata=-9999,
    )

    # these assets are needed by the flowmap
    current_assets = []
    for file in current_tiff_filenames:
        current_asset = args.assetfolder[0] + "/currents/" + file.replace(".tif", "")
        taskid = upload_to_gee(
            file,
            bucket,
            current_asset,
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        current_assets.append(current_asset)
        taskids.append(taskid)

    wind_tiff_filenames = glossis_wind_to_tiff(bucket, args.prefix[0], tmpdir)

    for file in wind_tiff_filenames:
        taskid = upload_to_gee(
            file,
            bucket,
            args.assetfolder[0] + "/wind/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    waveheight_tiff_filenames = glossis_waveheight_to_tiff(
        bucket, args.prefix[0], tmpdir
    )

    for file in waveheight_tiff_filenames:
        taskid = upload_to_gee(
            file,
            bucket,
            args.assetfolder[0] + "/waveheight/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    # Wait for all the tasks to finish
    wait_gee_tasks(taskids)


    # This should result in flowmap tiff files
    # The currents from glossis are converted to a tiff file that contains the flowmap  (rgb-encoded vector field)
    flowmap_task_ids = []
    flowmap_tiffs = []
    for current_asset in current_assets:
        flowmap_tiff = pathlib.Path(current_asset).with_suffix('.tif').name
        flowmap_tiffs.append(flowmap_tiff)
        task_id = export_flowmap(current_asset, bucket)
        flowmap_task_ids.append(task_id)
    wait_gee_tasks(flowmap_task_ids)

    # This should result in flowmap tiles in a bucket
    # The flowmaps are tiled using a rather specific tile format
    # These  are  uploaded to the public bucket
    flowmap_tiles_task_ids = []
    for flowmap_tiff in flowmap_tiffs:
        tile_dir = generate_wgs84_tiles(flowmap_tiff)
        upload_dir_to_bucket(public_bucket_name, source_dir_name=tile_dir, destination_dir_name='flowmaps')
        # TODO: how do we know which tiles are available in backend
