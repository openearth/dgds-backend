from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from google.cloud import storage
from datetime import datetime


def gloffis_weather_to_tiff(bucketname, prefixname, tmpdir):

    # Try downloading all files
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketname)
    blobs = storage_client.list_blobs(bucket)
    blobs = list(storage_client.list_blobs(bucket, prefix=prefixname))
    netcdfs = [blob.name for blob in blobs if blob.name.endswith(".nc") and "Export_Forecast_ECMWF-CF" in blob.name]
    print("Downloading the following files: {}".format(netcdfs))
    if len(netcdfs) != 1:
        raise Exception("We can only process 1 weather file.")

    netcdf = netcdfs[0]
    t = None  # automatically defined later
    variables = ['daily_precipitation', 'mean_temperature']
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

    for variable in variables:
        # Find timestamp for which data is not completely masked out
        if t is None:
            for i in range(len(nc.variables["time"])):
                data = nc.variables[variable][i, :, :]
                if not data.mask.all():
                    t = i
                    break
        else:
            data = nc.variables[variable][t, :, :]
        rasters.append(data)

    time = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)[t]
    print("Using non-empty timestamp {} at {}".format(i, time))
    analysis_time = \
        netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[0]

    # Add metadata and close file
    time_meta = {
        "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    dst_filename = "gloffis_weather_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))

    height, width = np.shape(rasters[0])
    divide = width // 2
    lons = np.array(nc.variables['y'])
    lats = np.array(nc.variables['x'])-180  # was 0 - 360
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
        # Reshuffle two slices of rasters
        newraster = np.empty_like(raster)
        newraster[:, 0:divide] = raster[:, divide:width]  # 180 - 360 moves to -180 to 0 (in front)
        newraster[:, divide:width] = raster[:, 0:divide]  # 0 - 180 stays the same (but is last now)

        dst.write_band(i + 1, newraster)
        dst.update_tags(i + 1, name=variables[i])

    dst.update_tags(**metadata)
    dst.update_tags(**time_meta)
    dst.close()
    return dst_filename


if __name__ == '__main__':
    gloffis_weather_to_tiff("dgds-data", "fews_gloffis/", "tmp/")
