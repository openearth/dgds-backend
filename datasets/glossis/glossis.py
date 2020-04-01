# -*- coding: utf-8 -*-

import argparse
import logging
from os import makedirs
from os.path import exists
from shutil import rmtree

from utils import fm_to_tiff, list_blobs, upload_to_gee, wait_gee_tasks
from waterlevel import create_water_level_astronomical_band
from waveheight import glossis_waveheight_to_tiff
from wind import glossis_wind_to_tiff

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
    # Setup directory
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    # clear items in gee folder in bucket
    old_blobs = list_blobs(args.bucket[0], "gee")
    for blob in old_blobs:
        blob.delete()
        logging.info(f"Blob {blob} deleted.")

    taskids = []

    waterlevel_tiff_filenames = fm_to_tiff(
        args.bucket[0],
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
            args.bucket[0],
            args.assetfolder[0] + "/waterlevel/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    current_tiff_filenames = fm_to_tiff(
        args.bucket[0],
        args.prefix[0],
        tmpdir,
        variables=["currents_u", "currents_v"],
        filter="currents",
        output_fn="glossis_currents",
        nodata=-9999,
    )

    for file in current_tiff_filenames:
        taskid = upload_to_gee(
            file,
            args.bucket[0],
            args.assetfolder[0] + "/currents/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    wind_tiff_filenames = glossis_wind_to_tiff(args.bucket[0], args.prefix[0], tmpdir)

    for file in wind_tiff_filenames:
        taskid = upload_to_gee(
            file,
            args.bucket[0],
            args.assetfolder[0] + "/wind/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    waveheight_tiff_filenames = glossis_waveheight_to_tiff(
        args.bucket[0], args.prefix[0], tmpdir
    )

    for file in waveheight_tiff_filenames:
        taskid = upload_to_gee(
            file,
            args.bucket[0],
            args.assetfolder[0] + "/waveheight/" + file.replace(".tif", ""),
            wait=False,
            force=True,
        )
        logging.info(f"Added task {taskid}")
        taskids.append(taskid)

    # Wait for all the tasks to finish
    wait_gee_tasks(taskids)
