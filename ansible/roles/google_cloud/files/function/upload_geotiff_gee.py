import glob
import os
import subprocess
from datetime import datetime
from google.cloud import storage
import rasterio
from os.path import basename
import sys

print(sys.executable, sys.version_info)
earth_engine_cli = "/env/bin/python3.7 /env/local/lib/python3.7/site-packages/ee/cli/eecli.py"


def run(cmd):
    print(cmd)
    subprocess.run(cmd)


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)


def upload_geotiff_gee(localfolder, bucket_name, bucket_folder):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """
    # bucket_name = "gs://dgds-data"
    file_types = ["currents", "waterlevel"]
    user = "rogersckw9"

    files = glob.glob(localfolder + '/*.tif')
    for f in files:
        print("Processing {}".format(f))

        fname = basename(f)
        upload_blob(bucket_name, f, bucket_folder+fname)

        fname = os.path.basename(f)
        fname_no_ext = os.path.splitext(fname)[0]

        # Get file type, either currents or waterlevel, to save to proper asset image collection
        file_type = [f for f in file_types if f in fname]

        # Get forecast datetime to assign asset from filename
        # forecast_datestring = fname_no_ext.split('_')[1]
        # forecast_date = datetime.strptime(forecast_datestring, "%Y%m%d%H%M%S")
        # forecast_datetime = forecast_date.strftime("%Y-%m-%dT%H:%M:%S")

        # Get datetime to assign to system:time_start for asset from filename
        # file_datestring = fname_no_ext.split('_')[1]
        # file_timestring = fname_no_ext.split('_')[2]
        # file_date = datetime.strptime(file_datestring + file_timestring, "%Y%m%d%H%M%S")
        # file_datetime = file_date.strftime("%Y-%m-%dT%H:%M:%S")

        gee_cmd = r"{} upload image --wait --asset_id=users/{}/dgds/GLOSSIS/{}/{} gs://{}/{}".format(
            earth_engine_cli,
            user,
            file_type[0],
            fname_no_ext,
            bucket_name,
            bucket_folder+fname)

        print(gee_cmd)
        run(gee_cmd)

        # add metadata
        src = rasterio.open(f)
        metadata = src.tags()
        gee_meta = r"{} asset set -p date_created={} " \
                   r"-p fews_build_number={} " \
                   r"-p fews_implementation_version={} " \
                   r"-p fews_patch_number={} " \
                   r"-p institution={} " \
                   r"-p system:time_start={} " \
                   r"-p forecast_time={} " \
                   r"users/{}/dgds/GLOSSIS/{}/{}".format(
            earth_engine_cli,
            metadata['date_created'],
            metadata['fews_build_number'],
            metadata['fews_implementation_version'],
            metadata['fews_patch_number'],
            metadata['institution'],
            metadata['system:time_start'],
            metadata['analysis_time'],
            user,
            file_type[0],
            fname_no_ext)

        print(gee_meta)
        run(gee_meta)


if __name__ == "__main__":
    main()
