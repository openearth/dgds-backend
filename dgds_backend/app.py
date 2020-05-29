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
from dgds_backend.providers_datasets import get_service_url, get_fews_url, get_hydroengine_url, DATASETS
from dgds_backend.schemas import DatasetSchema, TimeSerieSchema


app = Flask(__name__)
CORS(app)
cache = Cache(app, config={"CACHE_TYPE": "simple"})
app.config.update({
    "APISPEC_SPEC": APISpec(
        title="DGDS backend",
        openapi_version="2.0.0",
        version="1.0",
        plugins=[MarshmallowPlugin()],
    ),
    "APISPEC_SWAGGER_URL": "/swagger/",
})
docs = FlaskApiSpec(app)

# Configuration load
app.register_blueprint(error_handler.error_handler)
app.config.from_object("dgds_backend.default_settings")
try:
    app.config.from_envvar("DGDS_BACKEND_SETTINGS")
except (RuntimeError, FileNotFoundError) as e:
    print("Could not load config from environment variables")  # logging not set yet [could not read config]


# Logging setup
if not app.debug:
    from logging.handlers import TimedRotatingFileHandler

    # https://docs.python.org/3.6/library/logging.handlers.html#timedrotatingfilehandler
    file_handler = TimedRotatingFileHandler(os.path.join(app.config["LOG_DIR"], "dgds_backend.log"), "midnight")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("<%(asctime)s> <%(levelname)s> %(message)s"))
    app.logger.addHandler(file_handler)


@app.route("/locations", methods=["GET", "POST"])
@use_kwargs({"datasetId": fields.Str(required=True, validate=validate.OneOf(DATASETS["access"].keys()))})
def locations(**input):
    """
    Query locations
    """

    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = service_url_data["url"], service_url_data["name"], service_url_data["protocol"], service_url_data["parameters"]

    # Query PiService
    pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
    content = pi.get_locations(input)

    return jsonify(content)


@app.route("/timeseries", methods=["GET", "POST"])
@use_kwargs({"datasetId": fields.Str(required=True, validate=validate.OneOf(DATASETS["access"].keys())), "locationId": fields.Str(required=True), "startTime": fields.Str(), "endTime": fields.Str()})
@marshal_with(TimeSerieSchema(many=True))
def timeseries(**input):
    """
    Timeseries query
    """
    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = service_url_data["url"], service_url_data["name"], service_url_data["protocol"]

    # Query PiService
    if protocol == "dd-api":
        pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
        content = pi.get_timeseries(input)

    # Specific endpoint for DD like shoreline data
    elif protocol == "dd-api-shoreline":
        transect = input.get("locationId", None)
        content = dd_shoreline(data_url, transect, observation_type_id, input["datasetId"])

    # Specific endpoint for static images
    elif protocol == "staticimage":
        content = data_url.format(**input)

    else:
        error = "Unknown protocol in configuration."
        raise HTTPException(error)
        logging.error(error)

    return jsonify(content)


@app.route("/datasets", methods=["GET"])
@cache.cached(timeout=6 * 60 * 60, key_prefix="datasets")
@marshal_with(DatasetSchema(many=True))
def datasets():
    """
    Get datasets, populated with applicable urls for each dataset. Cached on 6hr intervals,
    based on time between new GLOSSIS files created
    """

    # Loop over datasets
    for datasetinfo in DATASETS["info"]["datasets"]:
        id = datasetinfo["id"]
        dataset_response = dataset(id, "")
        raster_layer = datasetinfo.get("rasterLayer", {})
        data = json.loads(dataset_response.data)
        raster_layer.update(data)
        datasetinfo['rasterLayer'] = raster_layer

    return jsonify(DATASETS["info"])


@app.route("/datasets/<string:datasetId>/<path:imageId>", methods=["GET"])
@cache.memoize(timeout=6 * 60 * 60)
def dataset(datasetId, imageId):
    service_url_data = get_service_url(datasetId, "rasterService")
    access_url = service_url_data["url"]
    feature_url = service_url_data["featureinfo_url"]
    name =  service_url_data["name"]
    protocol = service_url_data["protocol"]
    parameters = service_url_data["parameters"]
    range_min = request.args.get('min', None)
    range_max = request.args.get('max', None)
    if range_min:
        parameters['min'] = range_min
    if range_max:
        parameters['min'] = range_max

    if protocol == "fewsWms":
        data = get_fews_url(datasetId, name, access_url, feature_url, parameters)

    elif protocol == "hydroengine":
        data = get_hydroengine_url(datasetId, name, access_url, feature_url, parameters, image_id=imageId)

    else:
        logging.error("{} protocol not recognized for dataset datasetId {}".format(protocol, datasetId))
        data = {}

    return jsonify(data)


@app.route("/", methods=["GET"])
def root():
    """
    Redirect default page to API docs.
    """
    return redirect(url_for("flask-apispec.swagger-ui"))

docs.register(datasets)
docs.register(dataset)
docs.register(timeseries)
docs.register(locations)

def main():
    app.run(debug=False, threaded=True)


if __name__ == "__main__":
    main()
