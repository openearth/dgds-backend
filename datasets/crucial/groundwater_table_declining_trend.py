from os.path import basename, exists, join
import os

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime
from pathlib import Path

def groundwater_to_tiff(tmpdir):

    netcdfs = ['Groundwater_Table_Declining_Trend_historical_1950-01-31_to_2005-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2005-01-31_to_2014-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2015-01-31_to_2024-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2025-01-31_to_2034-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2035-01-31_to_2054-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2055-01-31_to_2065-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2035-01-31_to_2044-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp8p5_2045-01-31_to_2054-12-31.nc',
               'Groundwater_Table_Declining_Trend_rcp4p5_2005-01-31_to_2065-12-31.nc']
    
    variables = ['Groundwater_Table_Declining_Trend_1950-01-31_2005-12-31',
                 'Groundwater_Table_Declining_Trend_2005-01-31_2014-12-31',
                 'Groundwater_Table_Declining_Trend_2015-01-31_2024-12-31',
                 'Groundwater_Table_Declining_Trend_2025-01-31_2034-12-31',
                 'Groundwater_Table_Declining_Trend_2035-01-31_2054-12-31',
                 'Groundwater_Table_Declining_Trend_2055-01-31_2065-12-31',
                 'Groundwater_Table_Declining_Trend_2035-01-31_2044-12-31',
                 'Groundwater_Table_Declining_Trend_2045-01-31_2054-12-31',
                 'Groundwater_Table_Declining_Trend_2005-01-31_2065-12-31']

    # write to one geotiff file
    dst_filename = "Groundwater_Table_Declining_Trend.tif"

    ii=0

    # Combine data from multiple files: file 1
    rasters = []

    for netcdf in netcdfs:

        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        nc = netCDF4.Dataset(local_file, 'r')

        ## load data
        metadata = nc.__dict__

        variable = variables[ii]

        print("Processing variable " + variable + "in NetCDF file " + netcdf)

        rasters.append(nc.variables[variable][:, :])

        ii+=1

    height, width = np.shape(rasters[0])
    lons = np.array(nc.variables['lon'])
    lats = np.array(nc.variables['lat'])
    transform = from_bounds(lons.min(), lats.min(), lons.max(), lats.max(), width-1, height-1)

    dst = rasterio.open(
        dst_filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=9,
        dtype=rasters[0].dtype,
        crs='EPSG:4326',
        transform=transform
    )

    for i, raster in enumerate(rasters):
        print("write raster: " + str(i))
        dst.write_band(i + 1, raster)
        dst.update_tags(i + 1, name=variables[i])
    
    dst.close()

if __name__ == '__main__':
    groundwater_to_tiff(".")
