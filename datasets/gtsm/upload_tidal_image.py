import os
import subprocess

band_name_list = ["mean_sea_level",
                  "mean_higher_high_water",
                  "mean_lower_low_water",
                  "highest_astronomical_tide",
                  "lowest_astronomical_tide"]
band_names = ",".join(band_name_list)
asset_path = 'projects/dgds-gee/gtsm/tidal_indicators'
# File manually uploaded to storage bucket path:
bucket_path = 'gs://dgds-data/gtsm/gtsm_tidal_indicators.tif'
gee_cmd = r"earthengine --service_account_file {} --no-use_cloud_api upload image " \
              r"--bands {} --asset_id={} {}".format(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
        band_names,
        asset_path,
        bucket_path)
print(gee_cmd)
subprocess.run(gee_cmd, shell=True)
