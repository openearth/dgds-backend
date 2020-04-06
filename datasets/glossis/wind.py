from datetime import datetime
from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from google.cloud import storage
from rasterio.transform import from_bounds

from utils import download_netcdfs_from_bucket


def glossis_wind_to_tiff(bucketname, prefixname, tmpdir):

    # Get list of netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, "wind")

    if len(netcdfs) == 0:
        return []
        
    # Determine timesteps in first netcdf
    nc = netCDF4.Dataset(netcdfs[0])
    timesteps = netCDF4.num2date(
        nc.variables["time"][:], units=nc.variables["time"].units
    )

    if len(netcdfs) != 1:
        raise Exception("We can only process 1 windfile.")

    netcdf = netcdfs[0]
    variables = ["wind_u", "wind_v"]
    tiff_files = []

    for t, time in enumerate(timesteps):
        rasters = []

        print(
            "Processing {} timestep {}. Current time {}".format(
                netcdf, time, datetime.now()
            )
        )
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        nc = netCDF4.Dataset(local_file, "r")

        # load data
        metadata = nc.__dict__
        date_created = datetime.strptime(
            metadata["date_created"], "%Y-%m-%d %H:%M:%S %Z"
        )
        metadata["date_created"] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
        time = netCDF4.num2date(
            nc.variables["time"][:], units=nc.variables["time"].units
        )[t]
        analysis_time = netCDF4.num2date(
            nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units
        )[0]
        # Add metadata and close file
        time_meta = {
            "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        dst_filename = "glossis_wind_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))

        for variable in variables:
            rasters.append(nc.variables[variable][t, :, :])

        height, width = np.shape(rasters[0])
        lons = np.array(nc.variables["y"]) - 0.25
        lats = np.array(nc.variables["x"]) - 0.25
        transform = from_bounds(
            lats.min(), lons.max(), lats.max(), lons.min(), width - 1, height - 1
        )

        dst = rasterio.open(
            dst_filename,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=len(variables),
            dtype=rasters[0].dtype,
            crs=nc.variables["crs"].crs_wkt,
            transform=transform,
        )

        for i, raster in enumerate(rasters):
            dst.write_band(i + 1, raster)
            dst.update_tags(i + 1, name=variables[i])

        dst.update_tags(**metadata)
        dst.update_tags(**time_meta)
        dst.close()
        tiff_files.append(dst_filename)
    return tiff_files


if __name__ == "__main__":
    tiff_files = glossis_wind_to_tiff("dgds-data", "fews_glossis/", "/input/data/wind")
