# -*- coding: utf-8 -*-

import argparse
from os.path import basename, exists
from shutil import rmtree
from os import makedirs
import subprocess

from google.cloud import storage
import rasterio

from wind import glossis_wind_to_tiff
from waterlevel import glossis_waterlevel_to_tiff


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    print("Uploading from {} to {}/{}".format(source_file_name, bucket_name, destination_blob_name))
    blob.upload_from_filename(source_file_name)


def upload_to_gee(filename, bucket, asset):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """

    fname = basename(filename)
    bucketfname = "gee/" + fname
    upload_blob(bucket, filename, bucketfname)

    gee_cmd = r"earthengine --no-use_cloud_api upload image --wait --asset_id={} gs://{}/{}".format(
        asset,
        bucket,
        bucketfname)

    print(gee_cmd)
    subprocess.run(gee_cmd, shell=True)

    # add metadata
    src = rasterio.open(filename)
    metadata = src.tags()
    print(metadata)
    gee_meta = r"earthengine --no-use_cloud_api asset set -p date_created='{}' " \
               r"-p fews_build_number={} " \
               r"-p fews_implementation_version={} " \
               r"-p fews_patch_number={} " \
               r"-p institution={} " \
               r"{}".format(
                   metadata['date_created'],
                   metadata['fews_build_number'],
                   metadata['fews_implementation_version'],
                   metadata['fews_patch_number'],
                   metadata['institution'],
                   # metadata['system_time_start'],
                   # metadata['analysis_time'],
                   asset)

    print(gee_meta)
    subprocess.run(gee_meta, shell=True)


if __name__ == '__main__':

    # Setup CMD
    parser = argparse.ArgumentParser(
        description='Parse GLOSSIS netcdf output and upload to GEE.')
    parser.add_argument('bucket', type=str, nargs=1, help='Google bucket')
    parser.add_argument('prefix', type=str, nargs=1, help='Input folder/prefix', default="fews_glossis/")
    parser.add_argument('assetfolder', type=str, nargs=1, help='GEE asset')

    args = parser.parse_args()
    print(args.bucket)
    # Setup directory
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    waterlevel_tiff_fn = glossis_waterlevel_to_tiff(args.bucket[0], args.prefix[0], tmpdir)
    upload_to_gee(waterlevel_tiff_fn, args.bucket[0], args.assetfolder[0]+"/waterlevel/waterlevel")

    wind_tiff_fn = glossis_wind_to_tiff(args.bucket[0], args.prefix[0], tmpdir)
    upload_to_gee(wind_tiff_fn, args.bucket[0], args.assetfolder[0]+"/wind/wind")
