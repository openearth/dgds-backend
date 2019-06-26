import numpy as np
import geojson
import netCDF4
import os
import glob
import rasterio.features
from rasterio.transform import from_bounds

NODATA = -9999

# path to netCDF files to transform
path = os.path.join(os.getcwd(), "GLOSSIS/export/")
# get waterlevel files
files = glob.glob(path+"*waterlevel_00_fc.nc")
# take the first as a test
filename = files[0]
basename = os.path.basename(filename).split(".")[0]

# Get data and metadata
data = netCDF4.Dataset(filename)
metadata = data.__dict__

analysis_time = netCDF4.num2date(data.variables["analysis_time"][:], units=data.variables["analysis_time"].units)[0]
timesteps = netCDF4.num2date(data.variables["time"][:], units=data.variables["time"].units)

# Get the first time
t = 0
time = timesteps[t]
# set path to save geojson and geotiff files
save_path = path + basename + '_' + time.strftime("%Y%m%d_%H%M%S")

features = []
centroids = np.c_[data.variables["Mesh_face_x"][:], data.variables["Mesh_face_y"][:]]
water_level = data.variables["water_level"][t]
water_level_astronomical = data.variables["water_level_astronomical"][t]
# for each centroid, save water_levels to feature
for face_id, centroid in enumerate(centroids):
    water_level_i = water_level[face_id]
    water_level_astronomical_i = water_level_astronomical[face_id]
    feature = geojson.Feature(
        geometry=geojson.Point(
            coordinates=tuple(centroid)
        ),
        id=face_id,
        properties={
            "water_level": float(water_level_i),
            "water_level_astronomical": float(water_level_astronomical_i)
        }
    )
    features.append(feature)

# save feature collection to geojson
collection = geojson.FeatureCollection(features=features,
                                       properties=metadata
                                       )

with open(save_path +'.geojson', 'w') as f:
    geojson.dump(collection, f)

# rasterize the feature collection to WGS84 raster with 1000x1000 pixels
shapes = [
    (feature.geometry, feature.properties['water_level'])
    for feature
    in collection.features
]

transform = from_bounds(-180, -90, 180, 90, 1000, 1000)

raster = rasterio.features.rasterize(
    shapes,
    out_shape=(1000, 1000),
    transform=transform,
    fill=NODATA)

with rasterio.open(
        save_path + '.tif',
        'w',
        driver='GTiff',
        height=raster.shape[0],
        width=raster.shape[1],
        count=1,
        dtype=raster.dtype,
        crs='epsg:4326',
        transform=transform
) as dst:
    dst.write(raster, 1)