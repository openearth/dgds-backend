from os.path import basename, exists, join
import os

import netCDF4
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime


def chasm_wind_to_tiff(tmpdir):

    for root, dirs, files in os.walk("."):
      for filename in files:
        if filename.startswith("grasp"):
            print(filename)

            ## Try downloading all files
            # netcdfs = ["swanslices_20091028.nc"]
            netcdfs = [filename]
            if len(netcdfs) != 1:
                raise Exception("We can only process 1 file.")

            netcdf = netcdfs[0]

            for t in range(24):

                # t = 0
                # variables = ['hs']
                variables = ['wspeed','wdir']
                rasters = []

                print("Processing {}".format(netcdf))
                fn = basename(netcdf)
                local_file = join(tmpdir, fn)
                nc = netCDF4.Dataset(local_file, 'r')

                ## load data
                metadata = nc.__dict__
                # print(metadata)
                #date_created = datetime.strptime(metadata['date_created'], '%Y-%m-%d %H:%M:%S %Z')
                #metadata['date_created'] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
                time = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)[t]
                print(time)
                #analysis_time = \
                #    netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[t]
                ## Add metadata and close file
                #time_meta = {
                #    "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
                #    "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
                #}

                dst_filename = "chasm_grasplices_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))

                for variable in variables:
                    rasters.append(nc.variables[variable][t, 1, :, :])

                print(variables)

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
                    transform=transform
                )

                for i, raster in enumerate(rasters):
                    dst.write_band(i + 1, raster)
                    dst.update_tags(i + 1, name=variables[i])

                dst.close()
                #return dst_filename

if __name__ == '__main__':
    chasm_wind_to_tiff(".")
