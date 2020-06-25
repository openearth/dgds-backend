from os.path import basename, exists, join
import os

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime


def gtsm_to_tiff(tmpdir):

    for root, dirs, files in os.walk("."):
      for filename in files:
        if filename.startswith("gtsm_interpolate_tide_loop"):

            print(filename)

            ## Try downloading all files
            netcdfs = [filename]
            netcdf = netcdfs[0]

            variables = ['MSL','MHHW','MLLW','HAT','LAT']
            rasters = []

            print("Processing {}".format(netcdf))
            fn = basename(netcdf)
            local_file = join(tmpdir, fn)
            nc = netCDF4.Dataset(local_file, 'r')

            ## load data
            metadata = nc.__dict__

            dst_filename = "gtsm_tidal_indicators.tif"

            for variable in variables:
                rasters.append(nc.variables[variable][:, :])

                print(variables)

                height, width = np.shape(rasters[0])
                lons = np.array(nc.variables['lon'])
                lats = np.array(nc.variables['lat'])
                transform = from_bounds(lons.min(), lats.max(), lons.max(), lats.min(), width-1, height-1)

                dst = rasterio.open(
                    dst_filename,
                    'w',
                    driver='GTiff',
                    height=height,
                    width=width,
                    count=len(variables),
                    dtype=rasters[0].dtype,
                    crs='EPSG:4326',
                    transform=transform
            )

            for i, raster in enumerate(rasters):
                dst.write_band(i + 1, raster)
                dst.update_tags(i + 1, name=variables[i])

            dst.close()
            #return dst_filename

if __name__ == '__main__':
    gtsm_to_tiff(".")
