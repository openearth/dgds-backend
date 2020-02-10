from os.path import basename, exists, join
import math

from rasterio.transform import from_bounds
import numpy as np
import rasterio
import netCDF4
import numpy as np
import numpy.ma as ma
from matplotlib.tri import Triangulation, LinearTriInterpolator
from google.cloud import storage
from datetime import datetime

from utils import dflowgrid2tri
from utils import download_netcdfs_from_bucket

def glossis_currents_to_tiff(bucketname, prefixname, tmpdir, variables=["currents_u", "currents_v"], filter="currents"):

    # Get list of netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, filter)

    #Determine timesteps in first netcdf
    nc = netCDF4.Dataset(netcdfs[0])
    timesteps = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)
    print("Processing {} timesteps.".format(len(timesteps)))
    # processing of one timestep takes about 20 min.
    # now takes about 5 min, but still too slow
    # half of time is spent in interpolation
    # a third in the function itself
    # a sixth in triangulation
    timesteps = timesteps[0:1]
    tiff_files = []


    # Determine raster and cell coordinates
    # need 0.05 degree resolution for ground pixel, ~5.555km
    degree_resolution = 0.05
    minx, maxx, miny, maxy = -180, 180, -90, 90
    x = np.arange(minx, maxx + degree_resolution, degree_resolution)
    y = np.arange(miny, maxy + degree_resolution, degree_resolution)
    nx = len(x)
    ny = len(y)
    xv, yv = np.meshgrid(x, y)

    # Loop over all files (world is divided into 16 subgrids)
    for netcdf in netcdfs:
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
        analysis_time = \
            netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[0]

        # Determine triangles crossing over from -180 to 180
        # and remove these from the triangulation
        # TODO Add new nodes with flipped x coords and keep crossing triangles
        x = nc.variables['Mesh_node_x'][:]
        y = nc.variables['Mesh_node_y'][:]

        # Setup mask
        min_x, max_x = x.min(), x.max()
        min_y, max_y = y.min(), y.max()
        mask = (min_x <= xv) & (xv <= max_x) & (min_y <= yv) & (yv <= max_y)
        print("Mask has {} items of total raster {}.".format(np.count_nonzero(mask), nx*ny))

        triangles_x = x[triangles.astype(np.int64)]  # all x coordinates for each triangle dim(:, 3)
        left = (triangles_x < -90).any(axis=1)  # axis 1 has three triangle nodes
        right = (triangles_x > +90).any(axis=1)  # axis 1 has three triangle nodes
        crossing = np.array([left & right]).squeeze()
        triangles = triangles[~crossing, :]

        # Create interpolation and use it for interpolation
        # on all grid nodes. Ignore errors for now.
        triangulation = Triangulation(x, y, triangles)

        # Loop over variables (those with mesh_face/time dims)
        for ti, time in enumerate(timesteps):
            print("Processing {} timestep {}. Current time {}".format(netcdf, time, datetime.now()))
            rasters = {}
            for variable in variables:
                print("Processing variable {}. Current time {}".format(variable, datetime.now()))
                empty = np.empty((ny, nx))
                empty.fill(np.nan)
                rasters[variable] = empty

                # Retrieve variable and filter for crossing faces
                data_var = nc.variables[variable][ti, :]  # first timestep
                face_data = data_var[face_index.astype(np.int64)]
                face_data = face_data[~crossing]
                # plt.tripcolor(x, y, triangles, facecolors=face_data, edgecolors='k')

                # Assign the nodes of triangles the values from the faces of the
                # triangles. Current interpolation only works with nodes.
                # TODO Use interpolation in assigning values.
                node_data = np.zeros(x.shape)
                node_data.fill(-9999)
                for i, triangle in enumerate(triangles.astype(np.int64)):
                    for node in triangle:
                        # If node already has data, skip it
                        # nodes are shared by many triangles (~6)
                        if node_data[node] != -9999:
                            continue
                        # Assign face value to node
                        # unless it's masked out
                        z = face_data[i]
                        if np.ma.is_masked(z):
                            continue
                        node_data[node] = z

                try:
                    print("Setting up interpol. Current time {}".format(datetime.now()))

                    interp = LinearTriInterpolator(triangulation, node_data)
                    # interp = CubicTriInterpolator(triang, z_grid, kind="geom")
                except Exception as e:
                    print("File {} has an invalid mesh, output will have holes.".format())
                    print(e)
                    continue

                # Interpolate
                print("Interpol. Current time {}".format(datetime.now()))
                raster = interp(xv[mask], yv[mask])
                print("Done interpol. Current time {}".format(datetime.now()))
                rasters[variable][mask] = raster

            # Get time data and make file name
            time_meta = {
                "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),  # don't use : in key names
                "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
                }
            tiff_fn = "glossis_currents_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))
            tiff_files.append(tiff_fn)

            if exists(tiff_fn):

                dst = rasterio.open(tiff_fn, 'r+')

                # Write all variables to bands
                for i, (key, value) in enumerate(rasters.items()):
                    print("A. Current time {}".format(datetime.now()))
                    # merge raster with previous rasters
                    rraster = dst.read(i+1)
                    print("B. Current time {}".format(datetime.now()))
                    rraster[mask] = np.nanmax((rasters[variable][mask], rraster[mask]), axis=0)
                    print("C. Current time {}".format(datetime.now()))
                    dst.write_band(i + 1, rraster)
                    print("D. Current time {}".format(datetime.now()))
                dst.close()

            else:
                # Create TIFF
                transform = from_bounds(minx, maxy, maxx, miny, nx, ny)
                dst = rasterio.open(
                    tiff_fn,
                    'w',
                    driver='GTiff',
                    height=ny,
                    width=nx,
                    count=len(rasters.keys()),
                    dtype='float64',
                    crs='epsg:4326',
                    transform=transform,
                    tiled=True,
                    # compress="lzw"  # Don't compress for faster reading/writing
                )

                # Write all variables to bands
                for i, (key, value) in enumerate(rasters.items()):
                    dst.write_band(i + 1, value)
                    dst.update_tags(i + 1, name=key)

                # Add metadata and close file
                dst.update_tags(**metadata)
                dst.update_tags(**time_meta)
                dst.close()

    return tiff_files

if __name__ == '__main__':
    glossis_currents_to_tiff("dgds-data", "fews_glossis/", "./data/currents")
