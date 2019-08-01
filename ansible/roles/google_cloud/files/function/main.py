# -*- coding: utf-8 -*-
"""GCP Cloud storage trigger Function Example."""

import json
import datetime
import numpy as np
import geojson
import netCDF4
import os
import glob
import rasterio.features
from rasterio.transform import from_bounds
from google.cloud import storage
from os.path import basename, join, exists
import tempfile
from shutil import rmtree
from os import makedirs

# Local modules
from convert_glossis_netcdf_to_geotiff import convert_glossis_netcdf_to_geotiff
from upload_geotiff_gee import upload_geotiff_gee


def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    blob.download_to_filename(destination_file_name)

    print('Blob {} downloaded to {}.'.format(
        source_blob_name,
        destination_file_name))


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print('File {} uploaded to {}.'.format(
        source_file_name,
        destination_blob_name))


def convert_netcdf(data, context, prefix="fews_glossis"):
    """Background Cloud Function to be triggered by Cloud Storage.
       This generic function logs relevant data when a file is changed.

    Args:
        data (dict): The Cloud Functions event payload.
        context (google.cloud.functions.Context): Metadata of triggering event.
    Returns:
        None;
    """
    print('Event ID: {}'.format(context.event_id))
    print('Event type: {}'.format(context.event_type))
    print('Metageneration: {}'.format(data['metageneration']))
    print('Created: {}'.format(data['timeCreated']))
    print('Updated: {}'.format(data['updated']))

    print()
    if prefix in data['name']:
        convert_glossis_netcdf_bucket(data['bucket'], prefix)
    else:
        print("Trigger ignored ({} not in wrong {}).".format(data['name'], prefix))


def convert_glossis_netcdf_bucket(bucket, prefix):
    """Download all GLOSSIS .nc from the bucket and upload
    geotiffs to GEE when triggered in this folder.
    """

    # Setup directory
    tmpdir = "/tmp/netcdfs"
    if exists(tmpdir):
        rmtree(tmpdir)  # could remain from previous triggers
    makedirs(tmpdir)

    # Try downloading all files
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket)
    print(list(blobs))
    blobs = list(storage_client.list_blobs(bucket, prefix=prefix))
    print(blobs)
    netcdfs = [blob for blob in blobs if blob.endswith(".nc")]
    print("Downloading the following files: {}".format(netcdfs))

    for netcdf in netcdfs:
        fn = basename(netcdf)
        blob = bucket.blob(netcdf)
        blob.download_to_filename(join(tmpdir, fn))

    # Try converting to geotiff
    convert_glossis_netcdf_to_geotiff(tmpdir)

    # Upload geotiff to GEE
    upload_geotiff_gee(tmpdir, bucket, prefix)


if __name__ == "__main__":
    convert_glossis_netcdf_bucket("dgds-data", "/fews_glossis/")
