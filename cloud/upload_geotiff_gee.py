import os
import gdal, gdalconst
import glob
import subprocess

# Example of upload to Google Earth Engine via google storage buckets

def run(cmd):
    print(cmd)
    subprocess.run(cmd)

user = "gee_user_name@gmail.com"
input_dir = 'data/liwo-scenarios-03-2019/LIWO_Primair_tiffs'

files = glob.glob(input_dir + '/*.tif')
for f in files:
    fname = os.path.basename(f)
    fname_no_ext = os.path.splitext(fname)[0]
    gs_cmd = r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gsutil.cmd cp {0} gs://liwo-scenarios-03-2019/{1}".format(f,fname)
    run(gs_cmd)

    gee_cmd = r"earthengine upload image --wait --asset_id=users/rogersckw9/liwo/liwo-scenarios-03-2019/{0} gs://liwo-scenarios-03-2019/{1}".format(
        fname_no_ext,
        fname)
    run(gee_cmd)

    #     metadata
    src = gdal.Open(f, gdalconst.GA_ReadOnly)
    metadata = src.GetMetadata()
    gee_meta = r"earthengine asset set -p AREA_OR_POINT={0} " \
               r"-p BREACHNAME={1} " \
               r"-p LIWO_ID={2} " \
               r"-p XCOORD={3} " \
               r"-p YCOORD={4} " \
               r"users/rogersckw9/liwo/liwo-scenarios-03-2019/{5}".format(
        metadata['AREA_OR_POINT'], metadata['BREACHNAME'], metadata['LIWO_ID'], metadata['XCOORD'], metadata['YCOORD'], fname_no_ext)
    run(gee_meta)
