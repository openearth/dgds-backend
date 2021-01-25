from os.path import basename, exists, join
import os

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime


def evaporation_deficit_to_tiff(tmpdir):

    for root, dirs, files in os.walk("."):
      for filename in files:
        if filename.startswith("evaporation_deficit_C3S"):
            print(filename)

            ## Try downloading all files
            # netcdfs = ["evaporation_deficit_C3S-glob-agric_ERA5_month_20190101.nc"]
            netcdf = filename

            variables = ['evaporation_deficit']
            rasters = []

            print("Processing {}".format(netcdf))
            fn = basename(netcdf)
            local_file = join(tmpdir, fn)
            nc = netCDF4.Dataset(local_file, 'r')

            ## load data
            metadata = nc.__dict__

            yy = netcdf[46:50]
            mm = netcdf[50:52]
            print(yy)
            print(mm)

            dst_filename = "evaporation_deficit_{}{}01000000.tif".format(yy, mm)

            for variable in variables:
                rasters.append(nc.variables[variable][0, :, :])

                print(variable)

            height, width = np.shape(rasters[0])
            lons = np.array(nc.variables['x'])
            lats = np.array(nc.variables['y'])
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
                raster[raster==raster[1,1]]=np.nan
                dst.write_band(i + 1, raster)
                # print(raster[1000,2500])
                # print(raster[1,1])
                dst.update_tags(i + 1, name=variables[i])

            dst.close()
            #return dst_filename


if __name__ == '__main__':
    evaporation_deficit_to_tiff(".")
