import numpy as np
import numpy.ma as ma
from matplotlib.tri import Triangulation, LinearTriInterpolator
from google.cloud import storage
from os.path import basename, join

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
    
def download_netcdfs_from_bucket(bucketname, prefixname, tmpdir, parameter):

    # Try downloading all files
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketname)
    blobs = list(storage_client.list_blobs(bucket, prefix=prefixname))
    netcdfs = [blob.name for blob in blobs if blob.name.endswith(".nc") and parameter in blob.name]

    for netcdf in netcdfs:
        print("Downloading the following file: {}".format(netcdf))
        fn = basename(netcdf)
        local_file = join(tmpdir, fn)
        blob = bucket.blob(netcdf)
        blob.download_to_filename(local_file)

    return netcdfs
