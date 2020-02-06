# -*- coding: utf-8 -*-

import argparse
from os.path import basename, exists
from shutil import rmtree
from os import makedirs, environ
import subprocess
import logging

from google.cloud import storage
import rasterio

from wind import glossis_wind_to_tiff
from currents import glossis_currents_to_tiff
from waterlevel import glossis_waterlevel_to_tiff
from waveheight import glossis_waveheight_to_tiff


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    print("Uploading from {} to {}/{}".format(source_file_name,
                                              bucket_name, destination_blob_name))
    blob.upload_from_filename(source_file_name)


def list_blobs(bucket_name, folder_name):
    """Lists all the blobs in the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket, prefix=folder_name)

    return blobs


def wait_gee_tasks(tasks):
    for task in task:
        wait_gee_task(task)


def wait_gee_task(task):
    gee_cmd = "earthengine --service_account_file {creds} --no-use_cloud_api task wait {task}".format(
        task=task,
        creds=environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", default=""),
        )
    result = subprocess.run(gee_cmd, shell=True, capture_output=True, text=True)
    logging.warning(result)
    return result.stdout


def upload_to_gee(filename, bucket, asset, wait=True, force=False):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """

    swait = "--wait" if wait else ""
    sforce = "--force" if force else ""
    fname = basename(filename)
    bucketfname = "gee/" + fname
    upload_blob(bucket, filename, bucketfname)

    # add metadata
    src = rasterio.open(filename)
    metadata = src.tags()

    gee_cmd = r"earthengine --service_account_file {creds} --no-use_cloud_api upload image {wait} {force} --asset_id={asset} gs://{bucket}/{bucketfname}" \
        r"-p date_created='{date_created}' " \
        r"-p fews_build_number={fews_build_number} " \
        r"-p fews_implementation_version={fews_implementation_version} " \
        r"-p fews_patch_number={fews_patch_number} " \
        r"-p institution={institution} " \
        r"-p analysis_time={analysis_time} " \
        r"--time_start {system_time_start} " \
        "".format(
            wait=swait,
            force=sforce,
            creds=environ.get(
                "GOOGLE_APPLICATION_CREDENTIALS", default=""),
            asset=asset,
            bucket=bucket,
            bucketfname=bucketfname,
            **metadata)

    print(gee_cmd)
    result = subprocess.run(gee_cmd, shell=True, capture_output=True, text=True)
    pattern = "ID: "
    i = result.stdout.find(pattern)
    if i >= 0:
        taskid = result.stdout[i+len(pattern):].split("\n")[0]
    else:
        logging.error("No taskid found!")
        taskid = None

    return taskid


if __name__ == '__main__':

    # Setup CMD
    parser = argparse.ArgumentParser(
        description='Parse GLOSSIS netcdf output and upload to GEE.')
    parser.add_argument('bucket', type=str, nargs=1, help='Google bucket')
    parser.add_argument('prefix', type=str, nargs=1,
                        help='Input folder/prefix', default="fews_glossis/")
    parser.add_argument('assetfolder', type=str, nargs=1, help='GEE asset')

    args = parser.parse_args()
    print(args.bucket)
    # Setup directory
    tmpdir = "tmp/netcdfs/"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    # clear items in gee folder in bucket
    old_blobs = list_blobs(args.bucket[0], "gee")
    for blob in old_blobs:
        blob.delete()
        print('Blob {} deleted.'.format(blob))

    taskids = []

    waterlevel_tiff_filenames = glossis_waterlevel_to_tiff(
        args.bucket[0], args.prefix[0], tmpdir)

    for file in waterlevel_tiff_filenames:      
      taskid = upload_to_gee(file, args.bucket[0], args.assetfolder[0] +
                    "/waterlevel/" + file.replace(".tif", ""), wait=False, force=True)
      taskids.append(taskid)

    current_tiff_filenames = glossis_currents_to_tiff(
        args.bucket[0], args.prefix[0], tmpdir)

    for file in current_tiff_filenames:
      taskid = upload_to_gee(file, args.bucket[0], args.assetfolder[0] +
                  "/currents/" + file.replace(".tif", ""), wait=False, force=True)
      taskids.append(taskid)

    wind_tiff_filenames = glossis_wind_to_tiff(args.bucket[0], args.prefix[0], tmpdir)

    for file in wind_tiff_filenames:
      taskid = upload_to_gee(file, args.bucket[0], args.assetfolder[0] +
                  "/wind/" + file.replace(".tif", ""), wait=False, force=True)
      taskids.append(taskid)

    waveheight_tiff_filenames = glossis_waveheight_to_tiff(args.bucket[0], args.prefix[0], tmpdir)
    
    for file in waveheight_tiff_filenames:
      taskid = upload_to_gee(file, args.bucket[0], args.assetfolder[0] +
                  "/waveheight/" + file.replace(".tif", ""), wait=False, force=True)
      taskids.append(taskid)

    #Wait for all the tasks to finish
    wait_gee_tasks(taskids)
    