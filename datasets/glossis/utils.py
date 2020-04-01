from datetime import datetime
from os.path import basename, exists, join

import netCDF4
import numpy as np
import rasterio
from google.cloud import storage
from matplotlib.tri import LinearTriInterpolator, Triangulation
from rasterio.transform import from_bounds
import logging

def upload_dir_to_bucket(bucket_name, source_dir_name, destination_dir_name):
    """upload directory to a bucket"""
    cmd = "gsutil -m cp -r {source_dir_name} gs://{bucket_name}/{destination_dir_name}".format(
        bucket_name=bucket_name,
        source_dir_name=source_dir_name,
        destination_dir_name=destination_dir_name
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    logging.info(
        "Uploading from {} to {}/{}".format(
            source_file_name, bucket_name, destination_blob_name
        )
    )
    blob.upload_from_filename(source_file_name)


def list_blobs(bucket_name, folder_name):
    """Lists all the blobs in the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket, prefix=folder_name)

    return blobs


def wait_gee_tasks(tasks_ids):
    """Wait sequentially on all GEE tasks."""
    for task_id in tasks_ids:
        wait_gee_task(task_id)


def wait_gee_task(task_id):
    """Wait on GEE task given by task_id."""
    gee_cmd = "earthengine --service_account_file {creds} --no-use_cloud_api task wait {task}".format(
        task=task_id, creds=environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
    )
    result = subprocess.run(gee_cmd, shell=True, capture_output=True, text=True)
    logging.warning(result)
    return result.stdout


def upload_to_gee(filename, bucket, asset, wait=True, force=False):
    """
    Upload to Earth Engine via command line tool
    https://developers.google.com/earth-engine/command_line
    :return:
    """

    swait = "--wait" if wait else ""
    sforce = "--force" if force else ""
    fname = basename(filename)
    bucketfname = "gee/" + fname
    upload_blob(bucket, filename, bucketfname)

    # add metadata
    src = rasterio.open(filename)
    metadata = src.tags()

    gee_cmd = (
        r"earthengine --service_account_file {creds} --no-use_cloud_api upload image {wait} {force} --asset_id={asset} gs://{bucket}/{bucketfname}"
        r"-p date_created='{date_created}' "
        r"-p fews_build_number={fews_build_number} "
        r"-p fews_implementation_version={fews_implementation_version} "
        r"-p fews_patch_number={fews_patch_number} "
        r"-p institution={institution} "
        r"-p analysis_time={analysis_time} "
        r"--time_start {system_time_start} "
        "".format(
            wait=swait,
            force=sforce,
            creds=environ.get("GOOGLE_APPLICATION_CREDENTIALS", default=""),
            asset=asset,
            bucket=bucket,
            bucketfname=bucketfname,
            **metadata
        )
    )

    logging.info(gee_cmd)
    result = subprocess.run(gee_cmd, shell=True, capture_output=True, text=True)
    pattern = "ID: "
    i = result.stdout.find(pattern)
    if i >= 0:
        taskid = result.stdout[i + len(pattern) :].split("\n")[0]
    else:
        logging.error("No taskid found!")
        taskid = None

    return taskid


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
    tri[offset + np.arange(0, m4), 0:3] = mesh2d_face_nodes[
        np.ix_(index4[0], np.asarray([0, 2, 3]))
    ]
    index[offset + np.arange(0, m4)] = index4[0]
    offset = offset + m4

    # 5 nodes (2 extra triangles)
    if m5 > 0:
        tri[offset + np.arange(0, m5), 0:3] = mesh2d_face_nodes[
            np.ix_(index5[0], np.asarray([0, 2, 3]))
        ]
        index[offset + np.arange(0, m5)] = index5[0]
        offset = offset + m5

        tri[offset + np.arange(0, m5), 0:3] = mesh2d_face_nodes[
            np.ix_(index5[0], np.asarray([0, 3, 4]))
        ]
        index[offset + np.arange(0, m5)] = index5[0]
        offset = offset + m5

    # 6 nodes (3 extra triangles)
    if m6 > 0:
        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[
            np.ix_(index6[0], np.asarray([0, 2, 3]))
        ]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[
            np.ix_(index6[0], np.asarray([0, 3, 4]))
        ]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

        tri[offset + np.arange(0, m6), 0:3] = mesh2d_face_nodes[
            np.ix_(index6[0], np.asarray([0, 4, 5]))
        ]
        index[offset + np.arange(0, m6)] = index6[0]
        offset = offset + m6

    # remove 1 from the whole triangle matrix, as python is zero based, but D-Flow FM (Fortran) is 1 based.
    return {"triangles": tri - 1, "index": index}


def download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, parameter):
    """Download all .nc files with parameter in name from bucket with prefix to tmpdir."""

    # Try downloading all files
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketname)
    blobs = list(storage_client.list_blobs(bucket, prefix=prefixname))
    netcdfs = [
        blob.name
        for blob in blobs
        if blob.name.endswith(".nc") and parameter in blob.name
    ]

    local_files = []
    for netcdf in netcdfs:
        logging.info("Downloading the following file: {}".format(netcdf))
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        local_files.append(local_file)
        if not exists(local_file):
            blob = bucket.blob(netcdf)
            blob.download_to_filename(local_file)

    return local_files


def fm_to_tiff(
    bucketname,
    prefixname,
    tmpdir,
    variables=["currents_u", "currents_v"],
    filter="currents",
    output_fn="glossis_currents",
    nodata=-9999,
    extra_bands=0,
):
    """Convert FM netcdfs in bucket into geotiffs for each timestep."""

    # Get list of netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, filter)

    # Determine timesteps in first netcdf
    nc = netCDF4.Dataset(netcdfs[0])
    timesteps = netCDF4.num2date(
        nc.variables["time"][:], units=nc.variables["time"].units
    )
    logging.info(
        "{} timesteps of which only the first six will be processed.".format(
            len(timesteps)
        )
    )
    # After 6 timesteps (of an hour) we reach the timestamp
    # that will be overwritten by the next 6hourly run.
    timesteps = timesteps[0:6]
    tiff_files = []

    # Determine raster and cell coordinates
    # need 0.05 degree resolution for ground pixel, ~5.555km (at equator)
    degree_resolution = 0.05
    minx, maxx, miny, maxy = -180, 180, -90, 90
    # set x, y to the middle of raster cells
    x = np.arange(minx + degree_resolution / 2, maxx, degree_resolution)
    y = np.arange(miny + degree_resolution / 2, maxy, degree_resolution)
    nx = len(x)
    ny = len(y)
    xv, yv = np.meshgrid(x, y)

    # Loop over all files (world is divided into 16 subgrids)
    for netcdf in netcdfs:
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        nc = netCDF4.Dataset(local_file, "r")

        # Retrieve mesh structure and convert to triangles
        mesh2d_face_nodes = nc.variables["Mesh_face_nodes"][:]
        tridata = dflowgrid2tri(mesh2d_face_nodes)
        triangles, face_index = tridata["triangles"], tridata["index"]

        # Get the corresponding timestep
        metadata = nc.__dict__
        date_created = datetime.strptime(
            metadata["date_created"], "%Y-%m-%d %H:%M:%S %Z"
        )
        metadata["date_created"] = datetime.strftime(date_created, "%Y-%m-%dT%H:%M:%S")
        analysis_time = netCDF4.num2date(
            nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units
        )[0]

        # Determine triangles crossing over from -180 to 180
        # and remove these from the triangulation
        # TODO Add new nodes with flipped x coords and keep crossing triangles
        x = nc.variables["Mesh_node_x"][:]
        y = nc.variables["Mesh_node_y"][:]

        # Setup mask
        min_x, max_x = x.min(), x.max()
        min_y, max_y = y.min(), y.max()
        mask = (min_x <= xv) & (xv <= max_x) & (min_y <= yv) & (yv <= max_y)
        logging.info(
            "Mask has {:.2f}% of total raster.".format(
                np.count_nonzero(mask) / (nx * ny) * 100
            )
        )

        triangles_x = x[
            triangles.astype(np.int64)
        ]  # all x coordinates for each triangle dim(:, 3)
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
                    p = x[point] + 360, y[point]
                    if p not in unique_points:
                        x = np.append(x, p[0])
                        y = np.append(y, p[1])
                        pidx = len(x) - 1  # index of appended point
                        unique_points[p] = pidx
                    else:
                        pidx = unique_points[p]  # index of appended point

                    crossing_triangle[ip] = pidx

                else:
                    continue

            # Replace old triangle
            triangles[it] = crossing_triangle

        # Create interpolation and use it for interpolation
        # on all grid nodes. Ignore errors for now.
        triangulation = Triangulation(x, y, triangles)

        # Loop over variables (those with mesh_face/time dims)
        for ti, time in enumerate(timesteps):
            logging.info(
                "Processing {} timestep {}. Current time {}".format(
                    netcdf, time, datetime.now()
                )
            )
            rasters = {}
            for variable in variables:
                empty = np.empty((ny, nx))
                empty.fill(np.nan)
                rasters[variable] = empty

                # Retrieve variable and filter for crossing faces
                data_var = nc.variables[variable][ti, :]  # first timestep
                face_data = data_var[face_index]
                # plt.tripcolor(x, y, triangles, facecolors=face_data, edgecolors='k')

                # Assign the nodes of triangles the values from the faces of the
                # triangles. Current interpolation only works with nodes.
                # TODO Use interpolation in assigning values.
                node_data_dict = {}  # dict of node:[]
                for i, triangle in enumerate(triangles):
                    for node in triangle:
                        # Assign face value to node
                        z = face_data[i]

                        # nodes are shared by many triangles (~6)
                        if node in node_data_dict:
                            node_data_dict[node].append(z)
                        else:
                            node_data_dict[node] = [z]

                # Take max of surrounding face values (can become nan)
                node_data = np.zeros(x.shape)
                node_data.fill(nodata)
                for node, surrounding_face_values in node_data_dict.items():
                    node_data[node] = np.median(surrounding_face_values)

                try:
                    interp = LinearTriInterpolator(triangulation, node_data)
                except Exception as e:
                    logging.info(
                        "File {} has an invalid mesh ({}), output will have holes.".format(
                            local_file, e
                        )
                    )
                    continue

                # Interpolate
                raster = interp(xv[mask], yv[mask])
                rasters[variable][mask] = raster

            # Get time data and make file name
            time_meta = {
                "system_time_start": time.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                ),  # don't use : in key names
                "analysis_time": analysis_time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            tiff_fn = "{}_{}.tif".format(output_fn, time.strftime("%Y%m%d%H%M%S"))
            tiff_files.append(tiff_fn)

            if exists(tiff_fn):

                dst = rasterio.open(tiff_fn, "r+")

                # Write all variables to bands
                for i, (key, value) in enumerate(rasters.items()):
                    # merge raster with previous rasters
                    rraster = dst.read(i + 1)
                    rraster[mask] = np.nanmax(
                        (value[mask], rraster[mask]), axis=0
                    )
                    dst.write_band(i + 1, rraster)
                dst.close()

            else:
                # Create TIFF
                transform = from_bounds(minx, maxy, maxx, miny, nx, ny)
                dst = rasterio.open(
                    tiff_fn,
                    "w",
                    driver="GTiff",
                    height=ny,
                    width=nx,
                    count=len(rasters.keys()) + extra_bands,
                    dtype="float64",
                    crs="epsg:4326",
                    transform=transform,
                    tiled=True,
                    compress="packbits",
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
