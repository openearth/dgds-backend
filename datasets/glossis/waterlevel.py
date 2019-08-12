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


def dflowgrid2tri(mesh2d_face_nodes):
    """Convert the irregu2lar grid from a D-flow FM simulation
    into triangles only. It thus removes squares, pentagons and hexagons.

    mesh2d_face_nodes is two dimensional array of (faces, nodes=6) where
    node dimensions can contain NaNs when the face is not a hexagon.

    The output are triangles (triangles, nodes=3), and an index pointing
    to the original face for each triangle for data lookups. The number
    of triangles is neccessarily as long or longer than the input faces.
    """

    # Number of faces and a count of nodes of each face
    # including counts and indices of the different faces
    # in order to build the output arrays
    n = mesh2d_face_nodes.shape[0]
    count = np.sum(~np.isnan(mesh2d_face_nodes), axis=1)

    m4 = np.sum(count == 4)  # number of squares
    m5 = np.sum(count == 5)  # number of pentagons
    m6 = np.sum(count == 6)  # number of hexagons

    index3 = np.arange(0, n)
    index4 = np.where(count == 4)
    index5 = np.where(count == 5)
    index6 = np.where(count == 6)

    # Setup
    tri = np.zeros([n + m4 + 2 * m5 + 3 * m6, 3], dtype=np.int64)
    index = np.zeros(tri.shape[0], dtype=np.int64)

    # 3 nodes (all existing faces are triangles if cut off)
    tri[0:n, :] = mesh2d_face_nodes[0:n, 0:3]
    index[0:n] = index3
    offset = n

    # 4 nodes (1 extra triangle)
    tri[offset + np.arange(0, m4), 0:3] = mesh2d_face_nodes[np.ix_(index4[0], np.asarray([0, 2, 3]))]
    index[offset + np.arange(0, m4)] = index4[0]
    offset = offset + m4

    # 5 nodes (2 extra triangles)
    if m5 > 0:
        tri[offset + np.arange(0, m5), 0:3] = mesh2d_face_nodes[np.ix_(index5[0], np.asarray([0, 2, 3]))]
        index[offset + np.arange(0, m5)] = index5[0]
        offset = offset + m5

        tri[offset + np.arange(0, m5), 0:3] = mesh2d_face_nodes[np.ix_(index5[0], np.asarray([0, 3, 4]))]
        index[offset + np.arange(0, m5)] = index5[0]
        offset = offset + m5

    # 6 nodes (3 extra triangles)
    if m6 > 0:
        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[np.ix_(index6[0], np.asarray([0, 2, 3]))]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[np.ix_(index6[0], np.asarray([0, 3, 4]))]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[np.ix_(index6[0], np.asarray([0, 4, 5]))]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

    # remove 1 from the whole triangle matrix, as python is zero based, but D-Flow FM (Fortran) is 1 based.
    return {'triangles': tri - 1, 'index': index}


def glossis_waterlevel_to_tiff(bucketname, prefixname, tmpdir):

    # Try downloading all files
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketname)
    blobs = storage_client.list_blobs(bucket)
    blobs = list(storage_client.list_blobs(bucket, prefix=prefixname))
    netcdfs = [blob.name for blob in blobs if blob.name.endswith(".nc") and "waterlevel" in blob.name]
    print("Downloading the following files: {}".format(netcdfs))

    variables = ["water_level_surge", "water_level"]
    rasters = {k: [] for k in variables}

    # Determine raster and cell coordinates
    nx, ny = (361 * 5, 181 * 5)
    minx, maxx, miny, maxy = -180, 180, -90, 90
    x = np.linspace(minx, maxx, nx)
    y = np.linspace(miny, maxy, ny)
    xv, yv = np.meshgrid(x, y)
    t = 0
    nodata = -9999

    # Loop over all files (world is divided into 16 subgrids)
    for netcdf in netcdfs:
        print("Processing {}".format(netcdf))
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        blob = bucket.blob(netcdf)
        blob.download_to_filename(local_file)
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
            netCDF4.num2date(nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units)[t]

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
            rasters[variable].append(raster)

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
        transform=transform,
        nodata=nodata
    )

    # Write all variables to bands
    bands = {}
    for i, (key, value) in enumerate(rasters.items()):
        z = np.stack(value)
        z = np.nanmedian(z, axis=0)
        bands[key] = z
        dst.write_band(i + 1, z)
        dst.update_tags(i + 1, name=key)

    # Combine two variables into an extra band
    astro = np.subtract(bands["water_level"], bands["water_level_surge"])
    dst.write_band(3, astro)
    dst.update_tags(3, name="water_level_astronomical")

    dst.update_tags(**metadata)
    dst.update_tags(**time_meta)
    dst.close()
    return tiff_fn
