from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime, timedelta
from rasterio.windows import Window
from tqdm import tqdm
from matplotlib import pyplot

def elevation_to_tiff(fn, dst_filename):

    # Try downloading all files
    variables = ['elevation']
    variable = variables[0]
    # rasters = []

    nc = netCDF4.Dataset(fn, 'r')

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


    # for variable in variables:
    # rasters =

    dtime, height, width = nc.variables[variable].shape
    _, blockysize, blockxsize = nc.variables[variable].chunking()
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
        blockxsize=blockxsize,
        blockysize=blockysize,
        compress="deflate",
        predictor="2",
        BIGTIFF=True,
        NUM_THREADS="ALL_CPUS",
        DISCARD_LSB=2,
    )

    for ji, window in tqdm(list(dst.block_windows(1))):
        # TODO check axis order and correctness
        xslice, yslice = window.toslices()
        data = nc.variables[variable][0, yslice, xslice]
        dst.write_band(1, data, window=window)

    nc.close()
    dst.update_tags(1, name=variable)

    dst.update_tags(**metadata)
    dst.close()

    return dst_filename


if __name__ == '__main__':
    input = "/Users/evetion/MERIT_GEBCO.nc"
    output = "/Volumes/1TB_SSD/MERIT_GEBCO2.tif"
    print(elevation_to_tiff(input, output))
