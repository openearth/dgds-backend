from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime


def metocean_percentiles_to_tiff():

    # Try downloading all files
    variables = ['percentile_50', 'percentile_90']
    rasters = []

    local_file = "Percentiles.nc"
    nc = netCDF4.Dataset(local_file, 'r')

    # load data
    metadata = nc.__dict__
    date_created = datetime.strptime(metadata['history'], 'Created %a %b %d %H:%M:%S %Y')
    metadata['date_created'] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
    # Add metadata and close file

    dst_filename = "metocean_percentiles.tif"

    for variable in variables:
        rasters.append(nc.variables[variable][:, :])

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
        count=len(variables),
        dtype=rasters[0].dtype,
        crs=rasterio.crs.CRS.from_epsg(4326).to_wkt(),
        transform=transform,
        nodata=9969209968386869000000000000000000000.0
    )

    for i, raster in enumerate(rasters):
        newraster = raster
        dst.write_band(i + 1, raster)
        dst.update_tags(i + 1, name=variables[i])

    dst.update_tags(**metadata)
    dst.close()
    return dst_filename


if __name__ == '__main__':
    print(metocean_percentiles_to_tiff())
