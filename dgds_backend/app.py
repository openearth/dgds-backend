import json
import logging
import os
from datetime import datetime

import requests
from flask import Flask, url_for, redirect, make_response
from flask import request, jsonify, Response, abort
from apispec import APISpec
from flask_apispec import use_kwargs, marshal_with, doc
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
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
app.config.update({
    'APISPEC_SPEC': APISpec(
        title='DGDS backend',
        openapi_version="2.0.0",
        version="1.0",
        plugins=[MarshmallowPlugin()],
    ),
    'APISPEC_SWAGGER_URL': '/swagger/',
})
docs = FlaskApiSpec(app)

# Configuration load
app.register_blueprint(error_handler.error_handler)
app.config.from_object('dgds_backend.default_settings')
try:
    app.config.from_envvar('DGDS_BACKEND_SETTINGS')
except (RuntimeError, FileNotFoundError) as e:
    print('Could not load config from environment variables')  # logging not set yet [could not read config]


# Logging setup
if not app.debug:
    from logging.handlers import TimedRotatingFileHandler

    # https://docs.python.org/3.6/library/logging.handlers.html#timedrotatingfilehandler
    file_handler = TimedRotatingFileHandler(os.path.join(app.config['LOG_DIR'], 'dgds_backend.log'), 'midnight')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter('<%(asctime)s> <%(levelname)s> %(message)s'))
    app.logger.addHandler(file_handler)


@app.route('/locations', methods=["GET"])
def locations():
    """
    Query locations
    """
    # Read input [JSON] - Parameters from url
    input = request.args.to_dict(flat=True)

    # Get dataset identification
    msg, status, pi_service_url, observation_type_id, protocol, parameters = get_service_url(
        input['datasetId'], 'dataService')
    if status > 200:
        return jsonify(msg)

    # Query PiService
    pi = PiServiceDDL(observation_type_id, pi_service_url, request.url_root)
    content = pi.get_locations(input)

    return jsonify(content)


@app.route('/dummylocations', methods=["GET"])
def dummyLocations():
    """
    Dummy locations
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, 'dummy_data/dummyLocations.json')) as f:
        content = json.load(f)
    return jsonify(content)


@app.route('/timeseries', methods=["GET", "POST"])
@use_kwargs({'datasetId': fields.Str(required=True, validate=validate.OneOf(DATASETS["access"].keys())), 'locationId': fields.Str(required=True)})
@marshal_with(TimeSerieSchema(many=True))
def timeseries(**input):
    """
    Timeseries query
    """
    # Get dataset identification
    msg, status, data_url, observation_type_id, protocol, parameters = get_service_url(
        input['datasetId'], 'dataService')
    if status > 200:
        return jsonify(msg)

    # Query PiService
    if protocol == "dd-api":
        pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
        content = pi.get_timeseries(input)

    # Specific endpoint for DD like shoreline data
    elif protocol == "dd-api-shoreline":
        transect = input.get("locationId", None)
        content = dd_shoreline(data_url, transect, observation_type_id, input['datasetId'])

    # Specific endpoint for static images
    elif protocol == "staticimage":
        content = data_url.format(**input)

    else:
        error = 'Unknown protocol in configuration.'
        raise HTTPException(error)
        logging.error(error)

    return jsonify(content)


@app.route('/dummytimeseries', methods=["GET"])
def dummyTimeseries():
    """
    Dummy timeseries
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, 'dummy_data/dummyTseries.json')) as f:
        content = json.load(f)
    return jsonify(content)


@app.route('/datasets', methods=["GET"])
@cache.cached(timeout=6 * 60 * 60, key_prefix='datasets')
@marshal_with(DatasetSchema(many=True))
def datasets():
    """
    Get datasets, populated with applicable urls for each dataset. Cached on 6hr intervals,
    based on time between new GLOSSIS files created
    """
    # Return dummy file contents
    input = request.args.to_dict(flat=True)

    # Loop over datasets
    for dataset in DATASETS['info']['datasets']:
        id = dataset['id']
        msg, status, access_url, name, protocol, parameters = get_service_url(id, 'rasterService')
        if protocol == "fewsWms":
            data = get_fews_url(id, name, access_url, parameters)
        elif protocol == 'hydroengine':
            data = get_hydroengine_url(id, name, access_url, parameters)
        else:
            logging.error('{} protocol not recognized for dataset id {}'.format(protocol, id))
            continue

        dataset.update({
            "rasterLayer": data
        })

    return jsonify(DATASETS['info'])


@app.route('/', methods=["GET"])
def root():
    """
    Redirect default page to API docs.
    """
    return redirect(url_for('flask-apispec.swagger-ui'))

docs.register(datasets)
docs.register(timeseries)

def main():
    app.run(debug=False, threaded=True)


if __name__ == "__main__":
    main()
