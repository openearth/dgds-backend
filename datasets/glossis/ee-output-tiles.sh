#!/bin/bash

# This script syncs buckets

maxzoom=5
# Sync all the output data from EE  glossis-currents
gsutil -m rsync gs://dgds-flowmap/ee-output .
# Make a tiles  directory
mkdir tiles
# cd  to tiles
pushd tiles
# loop over all  output files
for f in ../glossis-current-*.tif*
do
    # convert to tiles
    python ~/src/dgds-backend/datasets/flowmap/glossis2wgs84-tiles.py --max-zoom $maxzoom $f
done
# go back
popd
# sync back to bucket
gsutil -m rsync -r tiles  gs://dgds-flowmap/tiles
