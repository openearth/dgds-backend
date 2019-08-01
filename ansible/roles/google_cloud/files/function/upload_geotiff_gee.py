import glob
import os
import subprocess
from datetime import datetime

# from osgeo import gdal
# from osgeo import gdalconst


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
        fname = os.path.basename(f)
        fname_no_ext = os.path.splitext(fname)[0]

        # Get file type, either currents or waterlevel, to save to proper asset image collection
        file_type = [f for f in file_types if f in fname]

        # Get forecast datetime to assign asset from filename
        forecast_datestring = fname_no_ext.split('_')[0]
        forecast_date = datetime.strptime(forecast_datestring, "%Y%m%d%H%M%S")
        forecast_datetime = forecast_date.strftime("%Y-%m-%dT%H:%M:%S")

        # Get datetime to assign to system:time_start for asset from filename
        file_datestring = fname_no_ext.split('_')[4]
        file_timestring = fname_no_ext.split('_')[5]
        file_date = datetime.strptime(file_datestring + file_timestring, "%Y%m%d%H%M%S")
        file_datetime = file_date.strftime("%Y-%m-%dT%H:%M:%S")

        upload_blob(bucket_name, f, bucket_folder+fname)

        gee_cmd = r"earthengine upload image --wait --asset_id=users/{0}/dgds/GLOSSIS/{1}/{2} {3}/{4}".format(
            user,
            file_type[0],
            fname_no_ext,
            bucket_name,
            bucket_folder+fname)

        run(gee_cmd)

        # add metadata
        # src = gdal.Open(f, gdalconst.GA_ReadOnly)
        # metadata = src.GetMetadata()
        # gee_meta = r"earthengine asset set -p date_created={0} " \
        #            r"-p fews_build_number={1} " \
        #            r"-p fews_implementation_version={2} " \
        #            r"-p fews_patch_number={3} " \
        #            r"-p institution={4} " \
        #            r"-p system:time_start={5} " \
        #            r"-p forecast_time={6} " \
        #            r"users/{7}/dgds/GLOSSIS/{8}/{9}".format(
        #     metadata['date_created'],
        #     metadata['fews_build_number'],
        #     metadata['fews_implementation_version'],
        #     metadata['fews_patch_number'],
        #     metadata['institution'],
        #     file_datetime,
        #     forecast_datetime,
        #     user,
        #     file_type[0],
        #     fname_no_ext)

        run(gee_meta)


if __name__ == "__main__":
    main()
