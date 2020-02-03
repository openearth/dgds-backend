#!/usr/bin/env python
# coding: utf-8



import pathlib

import click
import rasterio
import numpy as np
import matplotlib.pyplot as plt

from PIL import Image

height = 180
width = 360


@click.command()
@click.argument('input', type=click.Path(exists=True))
@click.option('--max-zoom', type=int, default=4)
def cli(input, max_zoom):
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


if  __name__ == '__main__':
    cli()
