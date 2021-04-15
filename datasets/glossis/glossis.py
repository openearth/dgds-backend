# -*- coding: utf-8 -*-

import argparse
import logging
import pathlib
import os
import tempfile
from os import makedirs
from os.path import exists
from shutil import rmtree

import pandas as pd
# Imports the Cloud Logging client library
import google.cloud.logging


from utils import (
    cd,
    fm_to_tiff,
    list_blobs,
    upload_to_gee,
    list_gee_tasks,
    wait_gee_tasks,
    upload_dir_to_bucket,
    download_blob,
    list_assets_in_gee,
    list_assets_in_bucket,
    gcloud_init
)

from waterlevel import create_water_level_astronomical_band
from waveheight import glossis_waveheight_to_tiff
from wind import glossis_wind_to_tiff

# this file is in  camelCase notation for compatibility with .js code, rename to this naming convention
from glossis2flowmap import exportFlowmap as export_flowmap
from glossis2flowmap import generateWgs84Tiles as generate_wgs84_tiles

if __name__ == "__main__":
    # Instantiates a client
    client = google.cloud.logging.Client()

    # Retrieves a Cloud Logging handler based on the environment
    # you're running in and integrates the handler with the
    # Python logging module. By default this captures all logs
    # at INFO level and higher
    client.get_default_handler()
    client.setup_logging()

    logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger(__name__)

    # Setup CMD
    parser = argparse.ArgumentParser(
        description="Parse GLOSSIS netcdf output and upload to GEE."
    )
    parser.add_argument("bucket", type=str, nargs=1, help="Google bucket")
    parser.add_argument(
        "prefix", type=str, nargs=1, help="Input folder/prefix", default="fews_glossis/"
    )
    parser.add_argument("assetfolder", type=str, nargs=1, help="GEE asset")

    # TODO: change all these sections to separate commands and make sure they run independent
    # instead of creating one script to rule them all...
    parser.add_argument(
        "--waterlevel", dest="waterlevel", default=False, action="store_true"
    )
    parser.add_argument(
        "--wind", dest="wind", default=False, action="store_true"
    )
    parser.add_argument(
        "--currents", dest="currents", default=False, action="store_true"
    )s
    parser.add_argument(
        "--waves", dest="waves", default=False, action="store_true"
    )
    parser.add_argument(
        "--flowmap-tiffs", dest='flowmap_tiffs', default=False, action='store_true'
    )
    parser.add_argument(
        "--flowmap-tiles", dest='flowmap_tiles', default=False, action='store_true'
    )
    parser.add_argument(
        "--skip-flowmap-history", dest='skip_flowmap_history', default=False, action='store_true'
    )
    parser.add_argument(
        "--cleanup", dest='cleanup', default=False, action='store_true'
    )

    args = parser.parse_args()
    logging.info(args.bucket)

    bucket = args.bucket[0]
    public_bucket = args.bucket[0] + "-public"
    prefix = args.prefix[0]

    # Setup directory
    # TODO: Use a proper tempdir
    # See: https://docs.python.org/3/library/tempfile.html
    # See also details about temp files and docker here:
    # https://docs.docker.com/storage/tmpfs/
    # and linux in general in man mktemp
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    if args.cleanup:
        # clear items in gee folder in bucket
        # TODO: put in separate cleanup script
        old_blobs = list_blobs(bucket, "gee")
        for blob in old_blobs:
            blob.delete()
            logging.info(f"Blob {blob} deleted.")

    taskids = []
    if args.waterlevel:

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
                args.assetfolder[0] + "/waterlevel/" +
                file.replace(".tif", ""),
                wait=False,
                force=True,
            )
            logging.info(f"Added task {taskid}")
            taskids.append(taskid)
            
        # Wait for all the tasks to finish
        wait_gee_tasks(taskids)

    if args.currents:
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
            current_asset = (
                args.assetfolder[0] + "/currents/" + file.replace(".tif", "")
            )
            taskid = upload_to_gee(
                file, bucket, current_asset, wait=False, force=True,)
            logging.info(f"Added task {taskid}")
            current_assets.append(current_asset)
            # TODO: cleanup these are now mixed with the previous tasks
            taskids.append(taskid)

        # Wait for all the tasks to finish
        wait_gee_tasks(taskids)

    if args.wind:
        wind_tiff_filenames = glossis_wind_to_tiff(
            bucket, args.prefix[0], tmpdir)

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

        # Wait for all the tasks to finish
        wait_gee_tasks(taskids)

    if args.waves:

        waveheight_tiff_filenames = glossis_waveheight_to_tiff(
            bucket, args.prefix[0], tmpdir
        )

        for file in waveheight_tiff_filenames:
            taskid = upload_to_gee(
                file,
                bucket,
                args.assetfolder[0] + "/waveheight/" +
                file.replace(".tif", ""),
                wait=False,
                force=True,
            )
            logging.info(f"Added task {taskid}")
            taskids.append(taskid)

        # Wait for all the tasks to finish
        wait_gee_tasks(taskids)

    if args.flowmap_tiffs:

        # This should result in flowmap tiff files
        # The currents from glossis are converted to a tiff file that contains the flowmap  (rgb-encoded vector field)

        # list available assets
        current_asset_folder = args.assetfolder[0] + '/currents/'
        flowmap_tiff_folder = 'flowmap/glossis/tiffs'

        current_assets = list_assets_in_gee(current_asset_folder)
        flowmap_tiffs = list_blobs(bucket,flowmap_tiff_folder)
        list_flowmap_tiffs = ['gs://dgds-data/' + blob.name for blob in flowmap_tiffs]

        flowmap_tasks = list_gee_tasks(prefix='flowmap-glossis-tiffs')

        todo = pd.DataFrame(data=dict(current_asset=current_assets))
        done = pd.DataFrame(data=dict(flowmap_tiff=list_flowmap_tiffs, done=True))
        scheduled = pd.DataFrame(flowmap_tasks)


        # extract the date (last element after last _)
        todo['date'] = todo.current_asset.str.split('_').apply(lambda x: x[-1])
        # strip off last 2 digits
        todo['date_gee'] = todo['date'].apply(lambda x: x[:-2])
        todo['flowmap_tiff'] = todo['date_gee'].apply(
            lambda x: 'gs://dgds-data/flowmap/glossis/tiffs/glossis-current-{}.tif'.format(x)
        )

        # see which files are nto yet converted
        work = pd.merge(todo, done, left_on='flowmap_tiff',
                        right_on='flowmap_tiff', how='left')
        work = work[work.done != True]

        logger.info(
            'todo: {}, done: {}, work: {}'.format(
                todo.shape[0],
                done.shape[0],
                work.shape[0]
            )
        )
        current_assets = work['current_asset']

        if args.flowmap_history:

            # This should result in flowmap tiff files
            # The currents from glossis are converted to a tiff file that contains the flowmap  (rgb-encoded vector field)
            flowmap_task_ids = []
            for i, row in work.iterrows():
                current_asset = row.current_asset
                flowmap_tiff = row.flowmap_tiff
                logger.info('converting {} to {}'.format(
                    current_asset, flowmap_tiff))
                task = export_flowmap(current_asset, bucket)
                flowmap_task_ids.append(task.id)
            logger.info('list of tasks: {}'.format(flowmap_task_ids))
            wait_gee_tasks(flowmap_task_ids)

    if args.flowmap_tiles:
        # log in to google cloud
        gcloud_init()

        # lookup  existing tiffs
        flowmap_tiff_folder = 'flowmap/glossis/tiffs'
        flowmap_tiffs = list_blobs(bucket, flowmap_tiff_folder)
        list_flowmap_tiffs = ['gs://dgds-data/' + blob.name for blob in flowmap_tiffs]


        # lookup existing tiles
        flowmap_tiles_folder = 'flowmap/glossis/tiles'
        flowmap_tiles = list_assets_in_bucket('gs://' + public_bucket + '/' + flowmap_tiles_folder)
        flowmap_tiles = [path.rstrip('/') for path in flowmap_tiles]

        # create a dataframe with the list of tiffs (all that we could do)
        todo = pd.DataFrame(data=dict(flowmap_tiff=list_flowmap_tiffs))
        todo['path'] = todo.flowmap_tiff.apply(
            lambda x: pathlib.Path(x).name
        )

        # what is the corresponding tileset that we expect
        todo['flowmap_tile'] = todo.path.apply(
            lambda x: 'gs://' + str(
                (public_bucket / pathlib.Path(flowmap_tiles_folder) / x).with_suffix('')
            )
        )

        # create a list of tiles that we already have
        done = pd.DataFrame(data=dict(flowmap_tile=flowmap_tiles, done=True))

        # create lookup the work that is not done
        work = pd.merge(todo, done, on='flowmap_tile', how='left')
        work = work[work.done != True]

        logger.info(
            'todo: {}, done: {}, work: {}'.format(
                todo.shape[0],
                done.shape[0],
                work.shape[0]
            )
        )


        if not args.skip_flowmap_history:
            # This should result in flowmap tiles in a bucket
            # The flowmaps are tiled using a rather specific tile format
            # These are  uploaded to the public bucket
            # we're downloading some local files.
            # do this using a temporary directory
            # this will be cleaned up when we exit the context              
            for i, row in work.iterrows():
                flowmap_tiff = row.flowmap_tiff
                logger.info("downloading {}".format(
                    flowmap_tiff
                ))
                # write temp files to this directory
                # change to this directory and return once we're done
                with tempfile.TemporaryDirectory() as tmp_dir:
                    with cd(tmp_dir):
                        download_blob(flowmap_tiff)

                        tile_dir = generate_wgs84_tiles(row.path)
                        upload_dir_to_bucket(
                            public_bucket, source_dir_name=tile_dir, destination_dir_name="flowmap/glossis/tiles"
                        )
