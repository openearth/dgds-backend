#! /bin/bash
# settings
# local directory with the data to upload
export localfolder="/srv/mnt/glossis_test/export/Google"
export localfolder_gloffis="/srv/mnt/gloffis/latest/W3RA_05deg/ECMWF-CF"
export KUBECONFIG=~/.kube/kube.conf
export GOOGLE_APPLICATION_CREDENTIALS=~/google-credentials.json

# Remove all old files from folder
find ${localfolder} -type f -name '*.nc' -mmin +60 -exec rm {} \;

# Synch new files to Google bucket
~/gsutil/gsutil rsync -d ${localfolder} gs://dgds-data/fews_glossis &> google_log.txt 2>&1
~/gsutil/gsutil rsync -d ${localfolder_gloffis} gs://dgds-data/fews_gloffis

# Start processing on kubernetes cluster
~/kubectl apply -f ~/dgds/glossis.yml
~/kubectl apply -f ~/dgds/gloffis.yml
