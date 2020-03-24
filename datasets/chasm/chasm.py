# -*- coding: utf-8 -*-

from os.path import basename, exists
from os import environ
import subprocess
from datetime import datetime

from google.cloud import storage

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
    bandnames = ["significant_wave_height", "wave_direction"]
    # filename =
    fname = basename(filename)
    bucketfname = "gee/" + fname
    upload_blob(bucket, filename, bucketfname)

    gee_cmd = r"earthengine --service_account_file {} upload image --wait --bands {} --asset_id={} gs://{}/{}".format(
        environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
        ",".join(bandnames),
        asset,
        bucket,
        bucketfname)

    print(gee_cmd)
    subprocess.run(gee_cmd, shell=True)

    date_from_filename = datetime.strptime(filename, "chasm_%Y%m%d%H%M%S.tif")
    datestring = datetime.strftime(date_from_filename, "%Y-%m-%dT%H:%M:%S")

    gee_meta = r"earthengine --service_account_file {} asset set " \
               r"--time_start {} " \
               r"{}".format(
                   environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
                   datestring,
                   asset)

    print(gee_meta)
    subprocess.run(gee_meta, shell=True)


if __name__ == '__main__':
    bucket = "dgds-data"
    prefix = "chasm"
    assetfolder = "projects/dgds-gee/chasm/test/"
    tiff_file = "chasm_20090215010000.tif"

    upload_to_gee(tiff_file, bucket, assetfolder+tiff_file.replace(".tif", ""))
