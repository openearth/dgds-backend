# -*- coding: utf-8 -*-

from os.path import basename
from os import environ
import subprocess
from datetime import datetime
import glob

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


def upload_to_gee(filename, bucket, assetfolder):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """
    prefix = 'msfd/'
    fname = basename(filename)
    asset = assetfolder + fname.replace('.tif', '')
    bucketfname = prefix + fname

    if 'monthly_chlorophyll' in assetfolder:
        date_from_filename = datetime.strptime(fname, 'CHL_1km_%Y%m%d%H%M%S.tif')
        bandnames = ['mean_chlorophyll','P10_chlorophyll','P90_chlorophyll','P25_chlorophyll','P75_chlorophyll']
    else:
        raise ValueError(f'Incorrect asset type: {assetfolder}')


    upload_blob(bucket, filename, bucketfname)

    gee_cmd = r'earthengine --service_account_file {} --no-use_cloud_api upload image --wait --bands {} --asset_id={} gs://{}/{}'.format(
        environ.get('GOOGLE_APPLICATION_CREDENTIALS', default=''),
        ','.join(bandnames),
        asset,
        bucket,
        bucketfname)
    print(gee_cmd)
    subprocess.run(gee_cmd, shell=True)

    datestring = datetime.strftime(date_from_filename, '%Y-%m-%dT%H:%M:%S')
    gee_meta = r'earthengine --service_account_file {} --no-use_cloud_api asset set ' \
               r'--time_start {} ' \
               r'{}'.format(
                   environ.get('GOOGLE_APPLICATION_CREDENTIALS', default=''),
                   datestring,
                   asset)
    print(gee_meta)
    subprocess.run(gee_meta, shell=True)


if __name__ == '__main__':

    bucket = 'dgds-data'
    assetfolder = 'users/danieltwigt/msfd/monthly_chlorophyll/'

    # Local path to data
    tif_files = glob.glob('C:\\Users\\twigt_d\\DTwigt_GIT\\dgds-backend\\datasets\\msfd\\*.tif')

    # assetfolder = 'projects/dgds-gee/chasm/wind/'
    # Local path to data
    # tif_files = glob.glob('D:\\dgds-data\\chasm\\chasm_graspslices_geotiff\\*.tif')

    for tif_file in tif_files[0:1]:

        upload_to_gee(tif_file, bucket, assetfolder)
