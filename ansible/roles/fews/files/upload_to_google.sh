#!/bin/bash
# settings
# local directory with the data to upload
export localfolder="/opt/fews/datacollect/fromfss/Export/Google"
export localfolder_gloffis="/opt/fews/datacollect/tofss/Import/GLOFFIS"
export KUBECONFIG=/home/fews/kube.conf
export GOOGLE_APPLICATION_CREDENTIALS=/home/fews/google-credentials.json
export BOTO_CONFIG=/home/fews/boto

cd /opt/fews/datacollect/software/Upload

# Remove all old files from folder
find ${localfolder} -type f -name '*.nc' -mmin +60 -exec rm {} \;

# Sync new files to Google bucket
./gsutil/gsutil rsync -d ${localfolder} gs://dgds-data/fews_glossis &> google_log.txt 2>&1
./gsutil/gsutil rsync -d ${localfolder_gloffis} gs://dgds-data/fews_gloffis &> google_log.txt 2>&1

# Start processing on kubernetes cluster
./kubectl delete -f glossis_workflow.yml
./kubectl create -f glossis_workflow.yml
./kubectl delete -f gloffis.yml
./kubectl apply -f gloffis.yml
