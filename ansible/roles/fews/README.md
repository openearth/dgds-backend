# Instructions for manual FEWS additions
In a FEWS forecasting shell used for the creation
of dgds datasets, the following should be installed.

```
wget https://storage.googleapis.com/pub/gsutil.tar.gz
tar xfz gsutil.tar.gz -C $HOME
```

A .boto file should be place in the home directory,
you can retrieve this file from our safe. This file
uses *Interoperable storage access keys* in the cloud
storage project page to authenticate.

After model runs, the dgds data can be uploaded by using
```
~/gsutil/gsutil rsync -d /folder/to_sync gs://dgds-data/{{ glossis_bucket }}

kubectl apply -f glossis.yml
```
