# -*- coding: utf-8 -*-

import argparse
from os.path import basename, exists
from shutil import rmtree
from os import makedirs, environ
import subprocess

from google.cloud import storage
import rasterio

from weather import gloffis_weather_to_tiff
from hydro import gloffis_hydro_to_tiff


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    print("Uploading from {} to {}/{}".format(source_file_name, bucket_name, destination_blob_name))
    blob.upload_from_filename(source_file_name)


def list_blobs(bucket_name, folder_name):
    """Lists all the blobs in the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket, prefix=folder_name)

    return blobs

def upload_to_gee(filename, bucket, asset):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """

    fname = basename(filename)
    bucketfname = "gee/" + fname
    upload_blob(bucket, filename, bucketfname)

    src = rasterio.open(filename)
    gee_cmd = r"earthengine --service_account_file {} upload image --wait --bands {} --asset_id={} gs://{}/{}".format(
        environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
        ",".join([src.tags(i+1)["name"] for i in range(src.count)]),
        asset,
        bucket,
        bucketfname)

    print(gee_cmd)
    subprocess.run(gee_cmd, shell=True)

    # add metadata
    metadata = src.tags()
    print(metadata)
    gee_meta = r"earthengine --service_account_file {} asset set -p date_created='{}' " \
               r"-p fews_build_number={} " \
               r"-p fews_implementation_version={} " \
               r"-p institution='{}' " \
               r"-p analysis_time={} " \
               r"--time_start {} " \
               r"{}".format(
                   environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
                   metadata['date_created'],
                   metadata['fews_build_number'],
                   metadata['fews_implementation_version'],
                   metadata['institution'],
                   metadata['analysis_time'],
                   metadata['system_time_start'],
                   asset)

    print(gee_meta)
    subprocess.run(gee_meta, shell=True)


if __name__ == '__main__':

    # Setup CMD
    parser = argparse.ArgumentParser(
        description='Parse GLOFFIS netcdf output and upload to GEE.')
    parser.add_argument('bucket', type=str, nargs=1, help='Google bucket')
    parser.add_argument('prefix', type=str, nargs=1, help='Input folder/prefix', default="fews_gloffis/")
    parser.add_argument('assetfolder', type=str, nargs=1, help='GEE asset')
    parser.add_argument(
        "--weather", dest="weather", default=False, action="store_true"
    )
    parser.add_argument(
        "--hydro", dest="hydro", default=False, action="store_true"
    )
    parser.add_argument(
        "--cleanup", dest='cleanup', default=False, action='store_true'
    )

    args = parser.parse_args()
    print(args.bucket)
    # Setup directory
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    if args.cleanup:
        # clear items in gee folder in bucket
        old_blobs = list_blobs(args.bucket[0], "gee")
        for blob in old_blobs:
            blob.delete()
            print('Blob {} deleted.'.format(blob))

    if args.weather:
        weather_tiff_fn = gloffis_weather_to_tiff(args.bucket[0], args.prefix[0], tmpdir)
        upload_to_gee(weather_tiff_fn, args.bucket[0], args.assetfolder[0]+"/weather/"+weather_tiff_fn.replace(".tif", ""))

    if args.hydro:
        hydro_tiff_fn = gloffis_hydro_to_tiff(args.bucket[0], args.prefix[0], tmpdir)
        upload_to_gee(hydro_tiff_fn, args.bucket[0], args.assetfolder[0]+"/hydro/"+hydro_tiff_fn.replace(".tif", ""))
