import json
import logging
import os
from pathlib import Path

import requests
from flasgger import Swagger
from flasgger.utils import swag_from
from flask import Flask, url_for, redirect
from flask import request, jsonify
from flask_cors import CORS
from flask_caching import Cache
from werkzeug.exceptions import HTTPException

from dgds_backend import error_handler
from dgds_backend.dgds_pi_service_ddl import PiServiceDDL
from dgds_backend.dgds_shoreline_service import dd_shoreline

app = Flask(__name__)
Swagger(app)
CORS(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

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

# Load general settings
APP_DIR = Path(os.path.dirname(os.path.realpath(__file__)))

# Dataset settings
try:
    DATASETS = {}
    fnameDatasets = Path(APP_DIR / 'config_data' / 'datasets.json')
    fnameAccess = Path(APP_DIR / 'config_data' / 'datasets_access.json')
    with open(str(fnameDatasets), 'r') as fd:
        DATASETS['info'] = json.load(fd)  # str for python 3.4, works without on 3.6+
    with open(str(fnameAccess), 'r') as fa:
        DATASETS['access'] = json.load(fa)  # str for python 3.4, works without on 3.6+
except FileNotFoundError as e:
    logging.error('Missing datasets.json (%s) datasets_access.json (%s), please check your deployment settings',
                  fnameDatasets, fnameAccess)
    exit(-1)  # vital config needed


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response


# Get the associated service url to a dataset inside the params dict
def get_service_url(datasetId, serviceType):
    """
    Get dataset identification
    :param params:
    :return:
    """

    msg = {}
    status = 200
    service_url = None
    name = None
    protocol = None
    parameters = None
    try:
        service_url = DATASETS['access'][datasetId][serviceType]['url']
        name = DATASETS['access'][datasetId][serviceType]['name']
        protocol = DATASETS['access'][datasetId][serviceType]['protocol']
        parameters = DATASETS['access'][datasetId][serviceType]['parameters']
    except Exception as e:
        msg = 'The provided datasetId does not exist'
        raise error_handler.InvalidUsage(msg)

    return msg, status, service_url, name, protocol, parameters


def get_hydroengine_url(id, layer_name, access_url, parameters):
    """
    Get hydroengine url and other info
    :param id: dataset id, as defined in datasets.json and datasets_access.json
    :return: url
    """
    data = {}

    post_data = {
        "dataset": layer_name
    }

    if parameters["bandName"] != "":
        post_data["band"] = parameters["bandName"]

    resp = requests.post(url=access_url, json=post_data)
    if resp.status_code == 200:
        data = json.loads(resp.text)
        data['dateFormat'] = "YYYY-MM-DDTHH:mm:ss"
        # Remove unnecessary keys
        [data.pop(key, None) for key in ['dataset', 'mapid', 'token']]
    else:
        logging.error('Dataset id {} not reached. Error {}'.format(id, resp.status_code))

    return data


def get_fews_url(id, layer_name, access_url, parameters):
    """
    Get FEWS Pi WMS url by filling in template with latest time
    :param id: dataset id, as defined in datasets.json and datasets_access.json
    :param url_template: template of url to adjust
    :return: url
    """
    latest_date = None
    url = None
    format = None
    data = {}
    resp = requests.get(url=access_url)
    if resp.status_code == 200:
        fews_data = json.loads(resp.text)
        # ignore layers in hydroengine
        for layer in fews_data['layers']:
            if layer['name'] == layer_name:
                url_template = parameters['urlTemplate']
                times = layer['times']
                latest_date = times[-1]
                url = url_template.replace('##TIME##', latest_date)
                format = "YYYY-MM-DDTHH:mm:ssZ"
            else:
                continue
    else:
        logging.error('Dataset id {} not reached. Error {}'.format(id, resp.status_code))

    data['date'] = latest_date
    data['dateFormat'] = format
    data['url'] = url
    return data


@app.route('/locations', methods=['GET'])
@swag_from('locations.yaml')
def locations():
    """
    Query locations
    :return:
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


# Dummy locations - /dummylocations
@app.route('/dummylocations', methods=['GET'])
def dummyLocations():
    """
    Dummy locations
    :return:
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, 'dummy_data/dummyLocations.json')) as f:
        content = json.load(f)
    return jsonify(content)


@app.route('/timeseries', methods=['GET'])
# @swag_from('locations.yaml')
def timeseries():
    """
    Timeseries query
    :return:
    """
    # Read input [JSON] - Parameters from url
    input = request.args.to_dict(flat=True)

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
        transect = input.get("transect_id", None)
        if transect is None:
            raise HTTPException("Bad request, transect_id parameter is required.")
        content = dd_shoreline(data_url, transect, observation_type_id, input['datasetId'])

    else:
        error = 'Configuration error.'
        raise HTTPException(error)
        logging.error(error)

    return jsonify(content)


@app.route('/dummytimeseries', methods=['GET'])
def dummyTimeseries():
    """
    Dummy timeseries
    :return:
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, 'dummy_data/dummyTseries.json')) as f:
        content = json.load(f)
    return jsonify(content)


@app.route('/datasets', methods=['GET'])
@cache.cached(timeout=6 * 60 * 60, key_prefix='datasets')
def datasets():
    """
    Get datasets, populated with applicable urls for each dataset. Cached on 6hr intervals,
    based on time between new GLOSSIS files created
    :return:
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


@app.route('/', methods=['GET'])
def root():
    """
    Redirect default page to API docs.
    :return:
    """
    return redirect(url_for('flasgger.apidocs'))


def main():
    app.run(debug=False)


if __name__ == "__main__":
    main()
