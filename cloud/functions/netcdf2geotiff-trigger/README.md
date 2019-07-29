
## Deploy

In order to deploy the you endpoint simply run

```bash
serverless deploy -v
```

The expected result should be similar to:

```bash
Serverless: Packaging service...
Serverless: Excluding development dependencies...
Serverless: Compiling function "netcdfConverter"...
Serverless: Uploading artifacts...
Serverless: Artifacts successfully uploaded...
Serverless: Updating deployment...
Serverless: Checking deployment update progress...
...............................
Serverless: Done...
Service Information
service: netcdf-converter
project: dgds-i1000482-002
stage: dev
region: europe-west1

Deployed functions
netcdfConverter
  projects/dgds-i1000482-002/buckets/dgds-data
```

## Usage

You can now invoke the Cloud Function directly and even see the resulting log via

```bash
serverless invoke --function netcdfConverter --data '{"bucket": "dgds-data", "name": "glossis/201906181200_DflowFM_gtsm_currents_00_fc.nc", "metageneration": "test", "timeCreated": "test", "updated": "test"}'
```

And to check out the logs directly from sls, you can run the following:

```bash
serverless logs --function netcdfConverter

```


