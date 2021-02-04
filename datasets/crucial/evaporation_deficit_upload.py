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

def upload_to_gee(filename, bucket, assetfolder):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """
    prefix = 'crucial/'
    fname = basename(filename)
    asset = assetfolder + fname.replace('.tif', '')
    bucketfname = prefix + fname

    if 'evaporation_deficit' in assetfolder:
        date_from_filename = datetime.strptime(fname, 'evaporation_deficit_%Y%m%d%H%M%S.tif')
        bandnames = ['evaporation_deficit']
    else:
        raise ValueError(f'Incorrect asset type: {assetfolder}')


    # upload_blob(bucket, filename, bucketfname)

    gee_cmd = r'earthengine --service_account_file {} upload image --wait --bands {} --asset_id={} gs://{}/{}'.format(
        environ.get('GOOGLE_APPLICATION_CREDENTIALS', default=''),
        ','.join(bandnames),
        asset,
        bucket,
        bucketfname)
    print(gee_cmd)
    subprocess.run(gee_cmd, shell=True)

    datestring = datetime.strftime(date_from_filename, '%Y-%m-%dT%H:%M:%S')
    gee_meta = r'earthengine --service_account_file {} asset set ' \
               r'--time_start {} ' \
               r'{}'.format(
                   environ.get('GOOGLE_APPLICATION_CREDENTIALS', default=''),
                   datestring,
                   asset)
    print(gee_meta)
    subprocess.run(gee_meta, shell=True)


if __name__ == '__main__':

    bucket = 'dgds-data'
    assetfolder = 'projects/dgds-gee/crucial/evaporation_deficit/'


    # Local path to data
    tif_files = glob.glob('c:\\Users\\twigt_d\\DTwigt_GIT\\dgds-backend\\datasets\\crucial\\evaporation_deficit_20190101000000.tif')

    for tif_file in tif_files[0:1]:

        upload_to_gee(tif_file, bucket, assetfolder)
