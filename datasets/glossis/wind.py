from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from google.cloud import storage
from datetime import datetime


def glossis_wind_to_tiff(bucketname, prefixname, tmpdir):

    # Try downloading all files
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketname)
    blobs = storage_client.list_blobs(bucket)
    blobs = list(storage_client.list_blobs(bucket, prefix=prefixname))
    netcdfs = [blob.name for blob in blobs if blob.name.endswith(".nc") and "wind" in blob.name]
    print("Downloading the following files: {}".format(netcdfs))
    if len(netcdfs) != 1:
        raise Exception("We can only process 1 windfile.")

    netcdf = netcdfs[0]
    t = 0
    variables = ['wind_u', 'wind_v']
    rasters = []

    print("Processing {}".format(netcdf))
    fn = basename(netcdf)
    local_file = join(tmpdir, fn)
    blob = bucket.blob(netcdf)
    blob.download_to_filename(local_file)
    nc = netCDF4.Dataset(local_file, 'r')

    # load data
    metadata = nc.__dict__
    date_created = datetime.strptime(metadata['date_created'], '%Y-%m-%d %H:%M:%S %Z')
    metadata['date_created'] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
    time = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)[t]
    analysis_time = \
        netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[t]
    # Add metadata and close file
    time_meta = {
        "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    dst_filename = "glossis_wind_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))

    for variable in variables:
        rasters.append(nc.variables[variable][t, :, :])

    height, width = np.shape(rasters[0])
    lons = np.array(nc.variables['y'])
    lats = np.array(nc.variables['x'])
    transform = from_bounds(lats.min(), lons.max(), lats.max(), lons.min(), width, height)

    dst = rasterio.open(
        dst_filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=len(variables),
        dtype=rasters[0].dtype,
        crs=nc.variables['crs'].crs_wkt,
        transform=transform
    )

    for i, raster in enumerate(rasters):
        dst.write_band(i + 1, raster)
        dst.update_tags(i + 1, name=variables[i])

    dst.update_tags(**metadata)
    dst.update_tags(**time_meta)
    dst.close()
    return dst_filename


if __name__ == '__main__':
    glossis_wind_to_tiff("test", "test", "test")
