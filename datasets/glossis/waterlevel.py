from os.path import basename, exists, join
import math

import glob

from rasterio.transform import from_bounds
import numpy as np
import rasterio
import netCDF4
import numpy as np
import numpy.ma as ma
from matplotlib.tri import Triangulation, LinearTriInterpolator
from datetime import datetime
from utils import dflowgrid2tri
from utils import download_netcdfs_from_bucket


def glossis_waterlevel_to_tiff(bucketname, prefixname, tmpdir):

    # Get list of netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, "waterlevel")

    #Determine timesteps in first netcdf
    nc = netCDF4.Dataset(join(tmpdir, netcdfs[0]))
    timesteps = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)
    # processing of one timestep takes about 20 min.
    timesteps = timesteps[0:6]

    variables = ["water_level_surge", "water_level"]
    tiff_files = []

    # Process netcdfs for each timestep in netcdf
    for t, time in enumerate(timesteps):
        rasters = {}

        # Determine raster and cell coordinates
        # need 0.05 degree resolution for ground pixel, ~5.555km
        degree_resolution = 0.05
        minx, maxx, miny, maxy = -180, 180, -90, 90
        x = np.arange(minx, maxx + degree_resolution, degree_resolution)
        y = np.arange(miny, maxy + degree_resolution, degree_resolution)
        nx = len(x)
        ny = len(y)
        xv, yv = np.meshgrid(x, y)

        
        # t = 0
        nodata = -9999

        # Loop over all files (world is divided into 16 subgrids)
        
        for netcdf in netcdfs:
            print("Processing {} timestep {}. Current time {}".format(netcdf, time, datetime.now()))
            fn = basename(netcdf)
            local_file = join(tmpdir, fn)
            nc = netCDF4.Dataset(local_file, 'r')

            # Retrieve mesh structure and convert to triangles
            mesh2d_face_nodes = nc.variables['Mesh_face_nodes'][:]
            tridata = dflowgrid2tri(mesh2d_face_nodes)
            triangles, face_index = tridata["triangles"], tridata["index"]

            # Get the corresponding timestep
            metadata = nc.__dict__
            date_created = datetime.strptime(metadata['date_created'], '%Y-%m-%d %H:%M:%S %Z')
            metadata['date_created'] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
            # timesteps = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)
            # time = timesteps[t]
            # time = t
            analysis_time = \
                netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[0]

            # Determine triangles crossing over from -180 to 180
            # and repair these to have a valid non crossing/
            # overlapping trianguliation
            x = nc.variables['Mesh_node_x'][:]
            y = nc.variables['Mesh_node_y'][:]
            triangles_x = x[triangles]  # all x coordinates for each triangle dim(:, 3)
            left = (triangles_x < -90).any(axis=1)  # axis 1 has three triangle nodes
            right = (triangles_x > +90).any(axis=1)  # axis 1 has three triangle nodes
            crossing = np.array([left & right]).squeeze()

            # Combine x, y so we won't duplicate points later
            unique_points = {x: i for (i, x) in enumerate(zip(x, y))}

            # For each triangle, check whether it's invalid
            # and if so, fix it by creating a new point at the
            # other side of the antimeridian and assigning it
            # to the triangle.
            for it, crossing_triangle in enumerate(triangles):

                # We can index directly and skip these checks
                # but then we lose the reference to the
                # original we want to replace later
                if not crossing[it]:  # ignore valid triangles
                    continue

                for ip, point in enumerate(crossing_triangle):
                    if x[point] < 0:  # only fix by moving points to the "right"

                        # Create new point and find its index
                        p = x[point]+360, y[point]
                        if p not in unique_points:
                            x = np.append(x, p[0])
                            y = np.append(y, p[1])
                            pidx = len(x)-1  # index of appended point
                            unique_points[p] = pidx
                        else:
                            pidx = unique_points[p]  # index of appended point

                        crossing_triangle[ip] = pidx

                    else:
                        continue

                # Replace old triangle
                triangles[it] = crossing_triangle

            # Loop over variables (those with mesh_face/time dims)
            for variable in variables:

                # Retrieve data variable
                data_var = nc.variables[variable][t, :]  # first timestep
                face_data = data_var[face_index]
                # plt.tripcolor(x, y, triangles, facecolors=face_data, edgecolors='k')

                # Assign the nodes of triangles the values from the faces of the
                # triangles. Current interpolation only works with nodes.
                # TODO Use interpolation in assigning values.
                node_data_dict = {}  # dict of node:[]
                for i, triangle in enumerate(triangles):
                    for node in triangle:
                        # Assign face value to node
                        # unless it's masked out
                        z = face_data[i]
                        if np.ma.is_masked(z):
                            continue

                        # nodes are shared by many triangles (~6)
                        if node in node_data_dict:
                            node_data_dict[node].append(z)
                        else:
                            node_data_dict[node] = [z]

                # Take median of surrounding face values
                # median is used to have an actual existing value
                node_data = np.zeros(x.shape)
                node_data.fill(nodata)
                for node, surrounding_face_values in node_data_dict.items():
                    node_data[node] = np.median(surrounding_face_values)

                # Create interpolation and use it for interpolation
                # on all grid nodes. Ignore errors for now.
                triangulation = Triangulation(x, y, triangles)
                try:
                    interp = LinearTriInterpolator(triangulation, node_data)
                    # interp = CubicTriInterpolator(triang, z_grid, kind="geom")
                except Exception as e:
                    print("File {} has an invalid mesh, output will have holes.".format())
                    print(e)
                    continue

                # Interpolate
                raster = interp(xv, yv)
                if variable not in rasters:
                    rasters[variable] = raster
                else:
                    # merge raster with previous rasters
                    raster_stack = np.stack((rasters[variable], raster))
                    rasters[variable] = np.nanmedian(raster_stack, axis=0)

        # Add metadata and close file
        time_meta = {
            "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),  # don't use : in key names
            "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        # Create TIFF
        tiff_fn = "glossis_waterlevel_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))
        transform = from_bounds(minx, maxy, maxx, miny, nx, ny)
        dst = rasterio.open(
            tiff_fn,
            'w',
            driver='GTiff',
            height=ny,
            width=nx,
            count=len(rasters.keys())+1,  # we add an extra band later
            dtype='float64',
            crs='epsg:4326',
            transform=transform
        )

        # Write all variables to bands
        for i, (key, value) in enumerate(rasters.items()):
            dst.write_band(i + 1, value)
            dst.update_tags(i + 1, name=key)

        # Combine two variables into an extra band
        astro = np.subtract(rasters["water_level"], rasters["water_level_surge"])
        dst.write_band(3, astro)
        dst.update_tags(3, name="water_level_astronomical")

        dst.update_tags(**metadata)
        dst.update_tags(**time_meta)
        dst.close()
        tiff_files.append(tiff_fn)

    return tiff_files

if __name__ == '__main__':
    glossis_waterlevel_to_tiff("dgds-data", "fews_glossis/", "/input/data")
