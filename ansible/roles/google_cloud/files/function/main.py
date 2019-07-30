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
import tempfile


def convert_netcdf(data, context):
    """Background Cloud Function to be triggered by Cloud Storage.
       This generic function logs relevant data when a file is changed.

    Args:
        data (dict): The Cloud Functions event payload.
        context (google.cloud.functions.Context): Metadata of triggering event.
    Returns:
        None;
    """

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(data['bucket'])
    blob = bucket.blob(data['name'])

    with tempfile.NamedTemporaryFile() as f:
        blob.download_to_filename(f.name)
        nc_data = netCDF4.Dataset(f.name)

    metadata = nc_data.__dict__

    print('NetCDF: {}'.format(metadata))
    print('--------------------------')
    print('Event ID: {}'.format(context.event_id))
    print('Event type: {}'.format(context.event_type))
    print('Bucket: {}'.format(data['bucket']))
    print('File: {}'.format(data['name']))
    print('Metageneration: {}'.format(data['metageneration']))
    print('Created: {}'.format(data['timeCreated']))
    print('Updated: {}'.format(data['updated']))
