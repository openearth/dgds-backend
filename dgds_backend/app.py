import json
import logging
import os
from datetime import datetime

import requests
from flask import Flask, url_for, redirect, make_response
from flask import request, jsonify, Response, abort
from apispec import APISpec
from flask_apispec import use_kwargs, marshal_with, doc
from webargs.flaskparser import use_args
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_apispec.extension import FlaskApiSpec
from flask_cors import CORS
from flask_caching import Cache
from marshmallow import fields, validate

from dgds_backend import error_handler
from dgds_backend.providers_timeseries import PiServiceDDL, dd_shoreline
from dgds_backend.providers_datasets import (
    get_service_url,
    get_fews_url,
    get_hydroengine_url,
    DATASETS,
    get_google_storage_url,
)
from dgds_backend.schemas import DatasetSchema, TimeSerieSchema


app = Flask(__name__)
CORS(app)
cache = Cache(app, config={"CACHE_TYPE": "simple"})
app.config.update(
    {
        "APISPEC_SPEC": APISpec(
            title="DGDS backend",
            openapi_version="2.0.0",
            version="1.0",
            plugins=[MarshmallowPlugin()],
        ),
        "APISPEC_SWAGGER_URL": "/swagger/",
    }
)
docs = FlaskApiSpec(app)

# Configuration load
app.config.from_object("dgds_backend.default_settings")
try:
    app.config.from_envvar("DGDS_BACKEND_SETTINGS")
except (RuntimeError, FileNotFoundError) as e:
    print(
        "Could not load config from environment variables"
    )  # logging not set yet [could not read config]

# only catch error if we're not in debug mode
if not app.debug:
    app.register_blueprint(error_handler.error_handler)

# Logging setup
if not app.debug:
    from logging.handlers import TimedRotatingFileHandler

    # https://docs.python.org/3.6/library/logging.handlers.html#timedrotatingfilehandler
    file_handler = TimedRotatingFileHandler(
        os.path.join(app.config["LOG_DIR"], "dgds_backend.log"), "midnight"
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("<%(asctime)s> <%(levelname)s> %(message)s")
    )
    app.logger.addHandler(file_handler)


@app.route("/locations", methods=["GET", "POST"])
@use_kwargs(
    {
        "datasetId": fields.Str(
            required=True, validate=validate.OneOf(DATASETS["access"].keys())
        )
    }
)
def locations(**input):
    """
    Query locations
    """

    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = (
        service_url_data["url"],
        service_url_data["name"],
        service_url_data["protocol"],
        service_url_data["parameters"],
    )

    # Query PiService
    pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
    content = pi.get_locations(input)

    return jsonify(content)


@app.route("/timeseries", methods=["GET", "POST"])
@use_kwargs(
    {
        "datasetId": fields.Str(
            required=True, validate=validate.OneOf(DATASETS["access"].keys())
        ),
        "locationId": fields.Str(required=True),
        "startTime": fields.Str(),
        "endTime": fields.Str(),
    }
)
@marshal_with(TimeSerieSchema(many=True))
def timeseries(**input):
    """
    Timeseries query
    """
    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = (
        service_url_data["url"],
        service_url_data["name"],
        service_url_data["protocol"],
    )

    # Query PiService
    if protocol == "dd-api":
        pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
        content = pi.get_timeseries(input)

    # Specific endpoint for DD like shoreline data
    elif protocol == "dd-api-shoreline":
        transect = input.get("locationId", None)
        content = dd_shoreline(
            data_url, transect, observation_type_id, input["datasetId"]
        )

    # Specific endpoint for static images
    elif protocol == "staticimage":
        content = data_url.format(**input)

    else:
        error = "Unknown protocol in configuration."
        raise HTTPException(error)
        logging.error(error)

    return jsonify(content)


@app.route("/datasets", methods=["GET"])
# cache this request so it returns the same result for 6 hours.
@cache.cached(timeout=6 * 60 * 60, key_prefix="datasets")
@marshal_with(DatasetSchema(many=True))
def datasets():
    """
    Get datasets, populated with applicable urls for each dataset. Cached on 6hr intervals,
    based on time between new GLOSSIS files created
    """
    # TODO: move this out of here and into a task (with celery or something)

    # Loop over datasets
    for datasetinfo in DATASETS["info"]["datasets"]:
        id = datasetinfo["id"]

        # we have datasetinfo from the json file
        # also get more information by calling the /dataset url
        data = dataset(id, None)

        # update the dataset with relevant info from the Url
        datasetinfo.update(data)

    #  all of the above is inline, so we can return the original object.
    return jsonify(DATASETS["info"])


@app.route("/datasets/<string:datasetId>/<path:imageId>", methods=["GET"])
@use_kwargs(
    {
        "min": fields.Int(required=False),
        "max": fields.Int(required=False),
        "band": fields.Str(required=False),
    }
)
def dataset_url(*args, **kwargs):
    return dataset(*args, **kwargs)


@cache.memoize(timeout=6 * 60 * 60)
def dataset(datasetId, imageId, **kwargs):
    service_url_data = get_service_url(datasetId, "rasterService")
    access_url = service_url_data["url"]
    feature_url = service_url_data["featureinfo_url"]
    name = service_url_data["name"]
    protocol = service_url_data["protocol"]
    parameters = service_url_data["parameters"]

    # Add any additional parameters given in request
    parameters.update(kwargs)

    if protocol == "fewsWms":
        data = get_fews_url(datasetId, name, access_url, feature_url, parameters)
    elif protocol == "hydroengine":
        data = get_hydroengine_url(
            datasetId, name, access_url, feature_url, parameters, image_id=imageId
        )

    else:
        logging.error(
            "{} protocol not recognized for dataset datasetId {}".format(
                protocol, datasetId
            )
        )
        data = {}

    dataset_dict = {}
    dataset_dict["rasterLayer"] = data

    # Populate flowmapLayer information
    service_url_data = get_service_url(datasetId, "flowmapService")
    if service_url_data:
        access_url = service_url_data["url"]
        name = service_url_data["name"]
        protocol = service_url_data["protocol"]
        parameters = service_url_data["parameters"]

        if protocol == "googlestorage":
            flowmap_data = get_google_storage_url(
                datasetId, name, access_url, parameters
            )
        else:
            logging.error(
                "{} protocol not recognized for flowmap datasetId {}".format(
                    protocol, datasetId
                )
            )
            flowmap_data = {}

        dataset_dict["flowmapLayer"] = flowmap_data

    return dataset_dict


@app.route("/", methods=["GET"])
def root():
    """
    Redirect default page to API docs.
    """
    return redirect(url_for("flask-apispec.swagger-ui"))


docs.register(datasets)
docs.register(dataset_url)
docs.register(timeseries)
docs.register(locations)


def main():
    app.run(debug=False, threaded=True)


if __name__ == "__main__":
    main()
