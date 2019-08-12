import json
import logging
import os
from pathlib import Path

import requests
from flasgger import Swagger
from flasgger.utils import swag_from
from flask import Flask
from flask import request, jsonify
from flask_cors import CORS
from flask_caching import Cache

from dgds_backend import error_handler
from dgds_backend.dgds_pi_service_ddl import PiServiceDDL

app = Flask(__name__)
Swagger(app)
CORS(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configuration load
app.register_blueprint(error_handler.error_handler)
app.config.from_object('dgds_backend.default_settings')
try:
    app.config.from_envvar('DGDS_BACKEND_SETTINGS')
except Exception as e:
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
except Exception as e:
    logging.error('Missing datasets.json (%s) datasets_access.json (%s), please check your deployment settings',
                  fnameDatasets, fnameAccess)
    exit(-1)  # vital config needed


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
    url = None
    date = None
    format = None

    post_data = {
        "dataset": layer_name
    }

    if parameters["bandNames"] is []:
        post_data["band"] = parameters["bandNames"]

    resp = requests.post(url=access_url, json=post_data)
    if resp.status_code == 200:
        data = json.loads(resp.text)
        url = data['url']
        date = data['date']
        format = "YYYY-MM-DDTHH:mm:ss"
    else:
        logging.error('Dataset id {} not reached. Error {}'.format(id, resp.status_code))

    return url, date, format

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

    resp = requests.get(url=access_url)
    if resp.status_code == 200:
        data = json.loads(resp.text)
        # ignore layers in hydroengine
        for layer in data['layers']:
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

    return url, latest_date, format

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
    msg, status, pi_service_url, observation_type_id, protocol, parameters = get_service_url(input['datasetId'], 'dataService')
    if status > 200:
        return jsonify(msg)

    # Query PiService
    pi = PiServiceDDL(observation_type_id, pi_service_url, request.url_root)
    content = {}
    try:
        content = pi.get_locations(input)
    except Exception as e:
        content = {'error': 'The PiService-DDL failed to serve the response. Please try again later'}
        logging.error('The PiService-DDL failed to serve the response. Please try again later')

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
def timeseries():
    """
    Timeseries query
    :return:
    """
    # Read input [JSON] - Parameters from url
    input = request.args.to_dict(flat=True)

    # Get dataset identification
    msg, status, pi_service_url, observation_type_id, protocol, parameters = get_service_url(input['datasetId'], 'dataService')
    if status > 200:
        return jsonify(msg)

    # Query PiService
    pi = PiServiceDDL(observation_type_id, pi_service_url, request.url_root)
    content = {}
    try:
        content = pi.get_timeseries(input)
    except Exception as e:
        content = {'error': 'The PiService-DDL failed to serve the response. Please try again later'}
        logging.error('The PiService-DDL failed to serve the response. Please try again later')

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
@cache.cached(timeout=6*60*60, key_prefix='datasets')
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
            url, date, format = get_fews_url(id, name, access_url, parameters)
        elif protocol == 'hydroengine':
            url, date, format = get_hydroengine_url(id, name, access_url, parameters)
        else:
            logging.error('{} protocol not recognized for dataset id {}'.format(protocol, id))
            continue

        dataset.update({
            "rasterLayer": {
                "url": url,
                "date": date,
                "dateFormat": format
            }
        })

    return jsonify(DATASETS['info'])


@app.route('/', methods=['GET'])
def root():
    """
    Redirect default page to API docs.
    :return:
    """
    msg = 'Welcome to DGDS'
    # print('redirecting ...')
    # return redirect(request.url + 'apidocs')
    return msg


def main():
    # initialize_app(app)
    # log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(debug=True)


if __name__ == "__main__":
    main()
