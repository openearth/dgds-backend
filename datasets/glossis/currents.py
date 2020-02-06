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

def glossis_currents_to_tiff(bucketname, prefixname, tmpdir):

    # Get list of netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, "currents")

    #Determine timesteps in first netcdf
    nc = netCDF4.Dataset(join(tmpdir, netcdfs[0]))
    timesteps = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)

    # processing of one timestep takes about 20 min.
    timesteps = timesteps[0:6]

    variables = ["currents_u", "currents_v"]
    tiff_files = []

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
        t = 0

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
            timesteps = netCDF4.num2date(nc.variables["time"][:], units=nc.variables["time"].units)
            time = timesteps[t]
            analysis_time = \
                netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[0]

            # Determine triangles crossing over from -180 to 180
            # and remove these from the triangulation
            # TODO Add new nodes with flipped x coords and keep crossing triangles
            x = nc.variables['Mesh_node_x'][:]
            y = nc.variables['Mesh_node_y'][:]
            triangles_x = x[triangles.astype(np.int64)]  # all x coordinates for each triangle dim(:, 3)
            left = (triangles_x < -90).any(axis=1)  # axis 1 has three triangle nodes
            right = (triangles_x > +90).any(axis=1)  # axis 1 has three triangle nodes
            crossing = np.array([left & right]).squeeze()
            triangles = triangles[~crossing, :]

            # Loop over variables (those with mesh_face/time dims)
            for variable in variables:

                # Retrieve variable and filter for crossing faces
                data_var = nc.variables[variable][t, :]  # first timestep
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

        # Get time data and make file name
        time_meta = {
            "system_time_start": time.strftime("%Y-%m-%dT%H:%M:%S"),  # don't use : in key names
            "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        tiff_fn = "glossis_currents_{}.tif".format(time.strftime("%Y%m%d%H%M%S"))

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
            transform=transform
        )

        # Write all variables to bands
        for i, (key, value) in enumerate(rasters.items()):
            dst.write_band(i + 1, value)
            dst.update_tags(i + 1, name=key)

        # Add metadata and close file
        dst.update_tags(**metadata)
        dst.update_tags(**time_meta)
        dst.close()
        tiff_files.append(tiff_fn)
    return tiff_files

if __name__ == '__main__':
    glossis_currents_to_tiff("dgds-data", "fews_glossis/", "/input/data/currents")
