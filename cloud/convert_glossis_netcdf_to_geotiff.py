import glob
import os
from pathlib import Path

import geojson
import netCDF4
import numpy as np
import pyugrid
import rasterio.features
import shapely.geometry
import shapely.ops
import tqdm
from rasterio.transform import from_bounds
from scipy.interpolate import griddata

import ipdb
# ipdb.set_trace() add to line
def ugrid(file):
    """Generate a ugrid grid from the input"""
    ugrid = pyugrid.UGrid.from_ncfile(file)

    faces = np.ma.asanyarray(ugrid.faces)

    # Don't use these, these are circumcenters
    face_centers = ugrid.face_coordinates

    nodes = ugrid.nodes
    # should be a ragged array
    face_coordinates = np.ma.asanyarray(nodes[faces])
    face_coordinates[faces.mask] = np.ma.masked

    # recompute face centers
    face_centroids = face_coordinates.mean(axis=1)

    x = nodes[:, 0]
    y = nodes[:, 1]
    z = np.zeros_like(x)
    points = np.c_[x, y, z]
    return dict(
        face_coordinates=face_coordinates,
        face_centers=face_centers,
        face_centroids=face_centroids,
        faces=faces,
        points=points
    )


def main():
    NODATA = -9999
    nx = 1000
    ny = 1000
    src_epsg = 4326
    dst_epsg = 4326
    crs = geojson.crs.Named(
        properties={
            "name": "urn:ogc:def:crs:EPSG::{:d}".format(src_epsg)
        }
    )
    transform = from_bounds(-180, -85, 180, 85, nx, ny)
    meridian = shapely.geometry.LineString([(-180, 90), (-180, -90)])
    layer_types = {
        "currents": ["currents_u", "currents_v"],
        "waterlevel": ["water_level", "water_level_astronomical"]
    }

    # path to netCDF files to transform
    # TODO: get google storage bucket path
    path = "D:/dgds-data/GLOSSIS/export/"
    # path = Path("./GLOSSIS/export")

    files = glob.glob(path + "*_00_fc.nc")

    # files generated every 6 hours, so only take first 6 timesteps of the file
    # times = range(6)
    # TODO: remove nested loops
    for t in range(6):
        # TODO: remove nested loops
        for f in files:
            # TODO: Convert to logging
            print("processing all files related to ", f)
            filename = os.path.basename(f).split(".")[0]
            searchname = filename.split("_00_fc")[0]
            match_files = glob.glob(path + searchname + "*.nc")
            value_string = None

            if "currents" in searchname:
                value_string = "currents"
            elif "waterlevel" in searchname:
                value_string = "waterlevel"
            else:
                print("variable not recognized")

            features = []
            polys = []

            # load all domains files with matching file names
            # TODO: remove nested loops
            for i, domain_file in enumerate(match_files):
                # load grid information in ugrid format
                grid = ugrid(domain_file)
                data = netCDF4.Dataset(domain_file)
                metadata = data.__dict__

                # TODO: split to other variables for units etc, more readable
                analysis_time = \
                    netCDF4.num2date(data.variables["analysis_time"][:], units=data.variables["analysis_time"].units)[0]
                timesteps = netCDF4.num2date(data.variables["time"][:], units=data.variables["time"].units)

                # Get the corresponding timestep
                time = timesteps[t]

                centroids = grid['face_centroids']
                variable_0 = data.variables[layer_types[value_string][0]][t]
                variable_1 = data.variables[layer_types[value_string][1]][t]
                print("processing file: ", domain_file)
                # get values for each face of grid, append to features
                for face_id, centroid in tqdm.tqdm(enumerate(centroids), desc='values->features'):
                    variable_0_i = variable_0[face_id]
                    variable_1_i = variable_1[face_id]
                    feature = geojson.Feature(
                        geometry=geojson.Point(
                            coordinates=tuple(centroid)
                        ),
                        id=face_id,
                        properties={
                            layer_types[value_string][0]: float(variable_0_i),
                            layer_types[value_string][1]: float(variable_1_i)
                            #             "time_analysis": float()
                        }
                    )
                    features.append(feature)

                # generate polygons of where grid exists for model mask
                faces = grid['faces']
                counts = (~faces.mask).sum(axis=1)
                face_coordinates = grid['face_coordinates']
                for i, (face, count) in tqdm.tqdm(enumerate(zip(face_coordinates, counts)), desc='grid->features'):
                    poly = shapely.geometry.Polygon(face[:count].tolist())
                    # polys.append(poly)
                    if meridian.intersects(poly):
                        # split_poly = shapely.ops.split(poly, meridian)
                        # for poly in split_poly.geoms:
                        #     ipdb.set_trace()
                        #     polys.append(poly)
                        old_coords = face[:count].tolist()
                        shift_coords = []
                        for x in old_coords:
                            shift_coords = shift_coords + [[x[0] + 360, x[1]]]
                        poly = shapely.geometry.Polygon(shift_coords)
                    polys.append(poly)

            collection = geojson.FeatureCollection(features=features,
                                                   properties=metadata
                                                   )
            save_path = path + searchname + '_' + time.strftime("%Y%m%d_%H%M%S")

            # with open(save_path +'.geojson', 'w') as f:
            #     geojson.dump(collection, f)

            # rasterize the feature collection to WGS84 raster with nx x ny pixels
            rasters = []
            for i, layer in enumerate(layer_types[value_string]):
                shapes = [
                    (feature.geometry, feature.properties[layer])
                    for feature
                    in collection.features
                ]

                raster = rasterio.features.rasterize(
                    shapes,
                    out_shape=(nx, ny),
                    transform=transform,
                    fill=NODATA
                )
                rasters.append(raster)

            # make model boundary mask as raster
            raster = rasterio.features.rasterize(
                ((poly, i) for (i, poly) in enumerate(polys)),
                out_shape=(nx, ny),
                transform=transform,
                fill=NODATA
            )

            rasters.append(raster)

            dst = rasterio.open(
                save_path + '_interpolated.tif',
                'w',
                **metadata,
                driver='GTiff',
                height=rasters[0].shape[0],
                width=rasters[0].shape[1],
                count=len(rasters),
                dtype='float64',
                crs='epsg:' + str(dst_epsg),
                transform=transform
            )
            for i, layer in enumerate(rasters):
                grid_x, grid_y = np.mgrid[0:nx, 0:ny]
                values = layer[layer != NODATA]
                grid_x_val = grid_x[layer != NODATA]
                grid_y_val = grid_y[layer != NODATA]
                if i <= 1:
                    points = np.column_stack([grid_x_val, grid_y_val])
                    interpolated = griddata(points, values, (grid_x, grid_y), method='linear')
                    dst.write_band(i + 1, interpolated)
                else:
                    is_grid = np.zeros((nx, ny), dtype='float64')
                    for x_, y_ in zip(grid_x_val, grid_y_val):
                        is_grid[x_, y_] = 1.0

                    dst.write_band(i + 1, is_grid)
            # time_meta = {
            #     "system:time_start": time.strftime("%Y%m%d %H%M%S"),
            #     "analysis_time": analysis_time.strftime("%Y%m%d %H%M%S")
            # }
            dst.update_tags(**metadata)
            # dst.update_tags(time_meta)
            dst.close()


if __name__ == "__main__":
    main()
