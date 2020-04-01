#!/usr/bin/env python
# coding: utf-8
import logging
import pathlib
import time

import click
import rasterio
import numpy as np
import matplotlib.pyplot as plt
import ee
import google.cloud.storage

from PIL import Image

logger = logging.getLogger(__name__)

def getWGS84Geometry():
    geometry = ee.Geometry.Polygon([
            [180,90],
            [0,90],
            [-180,90],
            [-180,-90],
            [0,-90],
            [180,-90],
            [180,90]
        ],
        'EPSG:4326',
        False
    )
    return geometry

def last(images):
    sorted = images.sort('system:time_start', False)
    last = sorted.first()
    return last

def tail(images, n):
    sorted = images.limit(n, 'system:time_start', False)
    return sorted


def computeFlowmap(currents):
    """Extract the timestamp for unique variable names  (assumes new instances are overwritten)"""
    timeStamp = currents.date().format("yyyyMMddHHmm")
    currents = currents.set('time_stamp', timeStamp)
    flowmap = currents.unitScale(-0.5, 0.5)

    # First deal with the mask
    # Create unmask and replace  mask by missing value
    flowmap = flowmap.unmask(-9999)

    # take  the mask
    mask = flowmap.eq(-9999).select('b1')
    # Create a smooth mask
    mask = mask.float()

    land = ee.Image("users/gena/land_polygons_image")

    mask = (
      mask
        .resample('bilinear')
        .where(land.mask(), 1)
        .unmask()
    )

    # convert to 0,1
    flowmap = flowmap.clamp(0, 1)
    flowmap = flowmap.resample('bilinear')

    flowmap = (
      flowmap
        .convolve(ee.Kernel.gaussian(30000, 20000, 'meters'))
    )

    flowmap = flowmap.addBands(mask)
    flowmap = flowmap.rename(['u', 'v', 'mask'])
    # Convert three  channels to rgb
    flowmapRgb = flowmap.visualize()
    flowmapRgb = ee.Image(
        flowmapRgb
          .copyProperties(currents)
    )
    return flowmapRgb



def exportFlowmap(currents_image_path, bucket):
    """export the last flowmap"""
    ee.Initialize()
    glossis = ee.ImageCollection("projects/dgds-gee/glossis/currents")

    region = getWGS84Geometry()

    currentImage = ee.Image(currents_image_path)

    flowmapRgb = computeFlowmap(currentImage)

    # Extract all time_stamps
    timeStamp = flowmapRgb.get('time_stamp').getInfo()

    exportFilename ='glossis-current' + '-' + timeStamp
    kwargs = {
        "image": flowmapRgb,
        "description": exportFilename + '-flowmap',
        "bucket": bucket,
        "fileNamePrefix": exportFilename,
        "dimensions": '8192x5760',
        "region": region,
        "crs": 'EPSG:4326'
    }
    logger.debug('exporting task {}'.format(kwargs))
    task = ee.batch.Export.image.toCloudStorage(**kwargs)

    task.start()

    return task

def downloadBlob(filename):
    bucket_name = 'deltares-video-map'

    client = google.cloud.storage.Client()
    bucket = client.get_bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.download_to_filename(filename)


def tiff2tiles(input, max_zoom=6):
    """convert a tiff file to a set of flowmap  tiles according to the windgl format"""
    # TODO: compute max_zoom

    # fixed settings
    height = 180
    width = 360

    ds = rasterio.open(input)

    input_path = pathlib.Path(input)

    currents_r = ds.read(1)
    currents_g = ds.read(2)
    currents_b = ds.read(3)

    rgb = np.dstack([currents_r[..., None], currents_g[..., None], currents_b[..., None]])

    stem = input_path.stem

    # store in folder with same name as file
    out_dir = pathlib.Path(stem)

    img = Image.fromarray(rgb)

    for zoom in range(0, max_zoom + 1):
        width_at_zoom  = 2**zoom * width
        height_at_zoom = 2**zoom * height
        img_at_zoom = np.asarray(img.resize((width_at_zoom, height_at_zoom)))
        for x in range(2 ** zoom):
            x_dir = out_dir / str(zoom) / str(x)
            x_dir.mkdir(parents=True, exist_ok=True)
            for y in range(2 ** zoom):

                filename =  x_dir / f"{y}.png"
                s = np.s_[(y * height):((y + 1) * height), (x * width):((x + 1) * width)]
                img_xyz = img_at_zoom[s]
                plt.imsave(filename, img_xyz)


@click.group()
def cli():
    logging.basicConfig(level=logging.DEBUG)

@cli.command()
@click.argument('filename')
def tiles(filename):
    downloadBlob(filename)
    tiff2tiles(filename)
    uploadBlob(pathlib.Path(filename.with_suffix('')))

@cli.command()
def flowmap():
    task = exportFlowmap()
    # wait for task to finish
    logger.info('Submitted  EE Task {}: {}'.format(task.id, task.name))
    # task submission is not received  (UNSUBMITTED), task is waiting  to run  (READY) or task is done (READY)
    while task.state in ('READY', 'RUNNING', 'UNSUBMITTED'):
        time.sleep(5)
        task.status()
    logger.info('EE Task {} completed with state {}'.format(task.id, task.state))

if  __name__ == '__main__':
    cli()
