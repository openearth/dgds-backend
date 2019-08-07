import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds

if __name__ == '__main__':
    dst_filename = "glossis_wind_test.tif"
    src_filename = "fews_glossis_2019080113_GFS_wind_fc.nc"

    # Use first time step
    t = 0
    variables = ['wind_u', 'wind_v']
    rasters = []

    # load data
    nc = netCDF4.Dataset(src_filename)
    metadata = nc.__dict__
    time = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)[t]
    analysis_time = \
        netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[t]

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

    # Add metadata and close file
    time_meta = {
        "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    dst.update_tags(**metadata)
    dst.update_tags(**time_meta)
    dst.close()
