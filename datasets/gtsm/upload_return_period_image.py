import os
import subprocess

band_name_list = ['waterlevel_2','waterlevel_5','waterlevel_10','waterlevel_25','waterlevel_50','waterlevel_75','waterlevel_100']
band_names = ",".join(band_name_list)
asset_path = 'projects/dgds-gee/gtsm/waterlevel_return_period'
# File manually uploaded to storage bucket path:
bucket_path = 'gs://dgds-data/gtsm/gtsm_waterlevel_return_period.tif'
gee_cmd = r"earthengine --service_account_file {} --no-use_cloud_api upload image " \
              r"--bands {} --asset_id={} {}".format(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
        band_names,
        asset_path,
        bucket_path)
print(gee_cmd)
subprocess.run(gee_cmd, shell=True)
