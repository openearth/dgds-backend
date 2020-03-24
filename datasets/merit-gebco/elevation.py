from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime, timedelta


def elevation_to_tiff():

    # Try downloading all files
    variables = ['elevation']
    variable = variables[0]
    # rasters = []

    local_file = "d:\\dgds-data\\bathymetry_elevation\\MERIT_GEBCO.nc"
    nc = netCDF4.Dataset(local_file, 'r')

    # load data
    metadata = nc.__dict__
    # date_created = datetime.strptime(metadata['time'], 'Created %a %b %d %H:%M:%S %Y')
    # metadata['date_created'] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
    days_since = nc.variables['time'][0].compressed()[0]
    units = nc.variables['time'].units
    ref_date = datetime.strptime(units, 'Days since %Y-%m-%d %H:%M:%S')
    date = ref_date + timedelta(days=days_since)
    # Add metadata and close file
    metadata['time'] = datetime.strftime(date, "%Y-%m-%dT%H:%M:%S")

    dst_filename = "MERIT_GEBCO.tif"

    # for variable in variables:
    # rasters =

    dtime, height, width = nc.variables[variable].shape
    lons = np.array(nc.variables['lon'])
    lats = np.array(nc.variables['lat'])

    transform = from_bounds(lons.min(), lats.min(), lons.max(), lats.max(), width-1, height-1)

    dst = rasterio.open(
        dst_filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=len(variables),
        dtype=nc.variables[variable].dtype,
        crs=rasterio.crs.CRS.from_epsg(4326).to_wkt(),
        transform=transform,
        nodata=-9999.0,
        tiled=True,
        compress="deflate"
    )

    # for i, raster in enumerate(rasters):
    #     newraster = raster
    dst.write_band(1, nc.variables[variable][0, :, :])
    nc.close()
    dst.update_tags(1, name=variable)

    dst.update_tags(**metadata)
    dst.close()
    return dst_filename


if __name__ == '__main__':
    print(elevation_to_tiff())
