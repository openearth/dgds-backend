from os.path import basename, exists, join
import os

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime


def msfd_to_tiff(tmpdir):

    files = ['CHL_1km_2002_2007',
             'CHL_1km_2003_2008',
             'CHL_1km_2004_2009',
             'CHL_1km_2005_2010',
             'CHL_1km_2006_2011',
             'CHL_1km_2007_2012',
             'CHL_1km_2008_2013',
             'CHL_1km_2009_2014',
             'CHL_1km_2010_2015',
             'CHL_1km_2011_2016',
             'CHL_1km_2012_2017',
             'CHL_1km_2013_2018',
             'CHL_1km_2014_2019']

    for file in files:

        ## Try downloading all files
        netcdf = file + ".nc"

        variables = ['mean_chlorophyll','P90_chlorophyll']
        rasters = []

        print("Processing {}".format(netcdf))
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        nc = netCDF4.Dataset(local_file, 'r')

        ## load data
        metadata = nc.__dict__

        dst_filename = file + ".tif"

        for variable in variables:
            nodata = nc.variables[variable][600, 600]
            var = nc.variables[variable][:, :]
            # set nodata value to 255, since nan values are not resolved properly in GEE
            var[var==nodata]=255
            rasters.append(var)

        height, width = np.shape(rasters[0])
        lons = np.array(nc.variables['longitude'])
        lats = np.array(nc.variables['latitude'])
        transform = from_bounds(lons.min(), lats.min(), lons.max(), lats.max(), width-1, height-1)

        dst = rasterio.open(
            dst_filename,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=len(variables),
            dtype=rasters[0].dtype,
            crs='EPSG:4326',
            nodata=255,
            transform=transform
        )

        for i, raster in enumerate(rasters):
            dst.write_band(i + 1, raster)
            dst.update_tags(i + 1, name=variables[i])

        dst.close()
        #return dst_filename


if __name__ == '__main__':
    msfd_to_tiff(".")
