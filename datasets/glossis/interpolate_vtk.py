#!/usr/bin/env python
# coding: utf-8

import logging
import pathlib
from datetime import datetime
import pandas as pd
from tvtk.api import tvtk
from tvtk.common import configure_input, configure_source_data
from tvtk.common import configure_connection, configure_input, configure_input_data, configure_outputs
import gridded 
import xarray as xr
import scipy.interpolate
import numpy as np
import netCDF4
import matplotlib.pyplot as plt
from cmcrameri import cm
import rasterio
from rasterio.transform import from_bounds

from utils import download_netcdfs_from_bucket

logger = logging.getLogger(__name__)

def grid2poly(grid):
    """ Read grid and convert to polydata """
    points = grid.nodes
    
    face_coords_mask = np.dstack([grid.faces.mask, grid.faces.mask])
    face_coords = np.ma.masked_array(
        grid.nodes[grid.faces], 
        face_coords_mask
    )

    # select faces that we need to duplicate
    # TODO: duplicate these (with nodes moved to other end of the world) (mod something...)
    x_max, y_max = face_coords.max(axis=(1)).T
    x_min, y_min = face_coords.min(axis=(1)).T
    mask = (x_min < -150) & (x_max > 150) 

    # Select faces
    faces = grid.faces[~mask]
    n_cells = faces.shape[0]
    cell_array = tvtk.CellArray()

    counts = (~faces.mask).sum(axis=1)
    assert faces.min() >= 0, 'expected 0 based faces'
    cell_idx = np.c_[counts, faces.filled(-999)].ravel()
    cell_idx = cell_idx[cell_idx != -999]
    cell_array.set_cells(n_cells, cell_idx)

    # fill in the properties
    polydata = tvtk.PolyData()
    # fill in z dimension
    polydata.points = np.c_[points, np.zeros_like(points[:, 0])]
    polydata.polys = cell_array
        
    return polydata, mask 

def update_data(path, polydata, mask, variables, t=0):
    """ Add arrays for each variable to polydata """
    ds = netCDF4.Dataset(path)
    for key in variables:
        arr = ds.variables[key][t, ...]

        array = tvtk.FloatArray()
        array.from_array(arr[~mask])
        array.name = key
        polydata.cell_data.add_array(array)
    polydata.modified()
    ds.close()

def setup_pipeline(polydata, width=1000, height=1000):
    """ VTk pipeline to resample data """
    resample = tvtk.ResampleToImage()
    cell2point = tvtk.CellDataToPointData()
    # setup the pipeline
    configure_input(cell2point, polydata)

    configure_input(resample, cell2point)

    resample.sampling_dimensions = np.array([width, height, 1])
    resample.sampling_bounds = np.array([-180, 180, -90, 90, 0, 0.0])
    resample.use_input_bounds = False
    # TODO: check if this can be left out
    resample.modified()
    resample.update()
    polydata.modified()

    return resample

def resample_data(netcdfs, img_size, t, variables):
    """ Resample data for timestep, variables in netcdf to given image size """
    polydatas_by_name = {}

    mbd = tvtk.MultiBlockDataSet()
    mbd.number_of_blocks = len(netcdfs)

    masks_by_name = {}

    for i, f in enumerate(netcdfs):
        ds = netCDF4.Dataset(f)
        grid = gridded.pyugrid.ugrid.UGrid.from_nc_dataset(ds)
        polydata, mask =  grid2poly(grid)
        mbd.set_block(i, polydata)
        masks_by_name[f.name] = mask
        polydatas_by_name[f.name] = polydata
        ds.close()

    mbm = tvtk.MultiBlockMergeFilter()
    configure_input_data(mbm, mbd)
    resample = setup_pipeline(mbm, width=img_size[0], height=img_size[1])

    for path in netcdfs:
        polydata = polydatas_by_name[path.name]
        mask = masks_by_name[path.name]
        update_data(path, polydata, mask, variables, t)
    resample.update()
    mbm.update()

    return resample

def fm_to_tiff_vtk(
    bucketname,
    prefixname,
    tmpdir,
    variables=["currents_u", "currents_v"],
    filter="currents",
    output_fn="glossis_currents",
    nodata=-9999,
    extra_bands=0,
):
    """Convert FM netcdfs in bucket into geotiffs for each timestep using vtk."""

    # Download netcdfs files from bucket
    netcdfs = download_netcdfs_from_bucket(
        bucketname, prefixname, tmpdir, filter)
    netcdfs = [pathlib.Path(netcdf) for netcdf in netcdfs]

    path = pathlib.Path('tmp/netcdfs')
    netcdfs = list(path.glob('*.nc'))
    
    if len(netcdfs) == 0:
        logger.warning(f"No {filter} files found!")
        return []

    # Determine timesteps in first netcdf
    nc = netCDF4.Dataset(netcdfs[0])
    timesteps = netCDF4.num2date(
        nc.variables["time"][:], units=nc.variables["time"].units
    )
    logger.info(
        "{} timesteps to be processed.".format(
            len(timesteps)
        )
    )

    metadata = nc.__dict__
    date_created = datetime.strptime(
        metadata["date_created"], "%Y-%m-%d %H:%M:%S %Z"
    )
    metadata["date_created"] = datetime.strftime(
        date_created, "%Y-%m-%dT%H:%M:%S")
    analysis_time = netCDF4.num2date(
        nc.variables["analysis_time"][:], units=nc.variables["analysis_time"].units
    )[0]

    img_size = (7200, 7200)

    tiff_files = []

    for ti, time in enumerate(timesteps):
        # TODO: Use grid, polygon from previous timestep instead of setting it up again each timestep
        logger.info("Processing timestep {}.".format(time))

        # Get the corresponding timestep 
        resample = resample_data(netcdfs, img_size, ti, variables)

        # Check variable names for each array in resampled output
        band_names = {}
        dimension = resample.output.data_dimension
        for i in list(range(dimension+1)):
            name = resample.get_output().point_data.get_array(i).name
            band_names[name] = i

        # Check if a mask is available in resampled output
        masked_data = False
        if 'vtkValidPointMask' in band_names:
            masked_data = True
            mask = resample.get_output().point_data.get_array(band_names['vtkValidPointMask']).to_array()
            mask = np.logical_not(mask.reshape(img_size))

        datetime_format = "%Y-%m-%dT%H:%M:%S"

         # Get time data and make file name
        time_meta = {
            "system_time_start": time.strftime(
                datetime_format
            ),  # don't use : in key names
            "analysis_time": analysis_time.strftime(datetime_format),
        }
        tiff_fn = "{}_{}.tif".format(
            output_fn, time.strftime("%Y%m%d%H%M%S"))

        tiff_files.append(tiff_fn)

        degree_resolution = 0.05
        minx, maxx, miny, maxy = -180, 180, -90, 90

        # set x, y to the middle of raster cells
        x = np.arange(minx + degree_resolution / 2, maxx, degree_resolution)
        y = np.arange(miny + degree_resolution / 2, maxy, degree_resolution)
        nx = len(x)
        ny = len(y)

        logger.info("Write {} file".format(tiff_fn))

        transform = from_bounds(minx, maxy, maxx, miny, nx, ny)
        dst = rasterio.open(
            tiff_fn,
            "w",
            driver="GTiff",
            height=ny,
            width=nx,
            count=len(variables) + extra_bands,
            dtype="float32",
            crs="epsg:4326",
            transform=transform,
            tiled=True,
            compress="deflate",
        )

        for i, variable in enumerate(variables):
            if variable in band_names:
                bn = band_names[variable]
                raster = resample.get_output().point_data.get_array(bn).to_array()
                raster = raster.reshape(img_size)
                if masked_data:
                    raster[mask] = np.nan
                dst.write_band(i + 1, raster)
                dst.update_tags(i + 1, name=variable)

        # Add metadata and close file
        dst.update_tags(**metadata)
        dst.update_tags(**time_meta)
        dst.close()

    return tiff_files
