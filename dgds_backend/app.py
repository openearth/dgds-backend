import json
import os

from flask import Flask
from flask import request, jsonify
from flasgger import Swagger
from flasgger.utils import swag_from

from dgds_backend import error_handler
from dgds_backend.dgds_pi_service_ddl import PiServiceDDL

app = Flask(__name__)
Swagger(app)
app.config.from_object('dgds_backend.default_settings')
app.config.from_envvar('DGDS_BACKEND_SETTINGS')
app.register_blueprint(error_handler.error_handler)

APP_DIR = os.path.dirname(os.path.realpath(__file__))
HOSTNAME_URL = 'http://{host}:{port}'.format(prot='http', host='localhost', port=5000)

if not app.debug:
    import logging
    from logging.handlers import TimedRotatingFileHandler

    # https://docs.python.org/3.6/library/logging.handlers.html#timedrotatingfilehandler
    file_handler = TimedRotatingFileHandler(os.path.join(app.config['LOG_DIR'], 'dgds_backend.log'), 'midnight')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter('<%(asctime)s> <%(levelname)s> %(message)s'))
    app.logger.addHandler(file_handler)

# Dataset settings
try:
    DATASETS = {}
    with open(os.path.join(APP_DIR, '..\config_data\datasets.json')) as fd:
        DATASETS['info'] = json.load(fd)
    with open(os.path.join(APP_DIR, '..\config_data\datasets_access.json')) as fa:
        DATASETS['access'] = json.load(fa)
except Exception as e:
    print('Missing datasets.json %s /datasets_access.json %s, please check your deployment settings', (fd, fa))
    exit(-1)  # vital config needed


# Get the associated service url to a dataset inside the params dict
def get_service_url(params):
    """
    Get dataset identification
    :param params:
    :return:
    """
    service_url = None
    protocol = None
    status = 200
    msg = {}
    try:
        if 'datasetId' in params:
            service_url = DATASETS['access'][params['datasetId']]['urlData']
            protocol = DATASETS['access'][params['datasetId']]['protocolData']
        else:
            msg = 'No datasetId specified in the request'
            raise error_handler.InvalidUsage(msg)
    except Exception as e:
        msg = 'The provided dataset does not exist'
        raise error_handler.InvalidUsage(msg)

    return msg, status, service_url, protocol


@app.route('/locations', methods=['GET'])
@swag_from('locations.yaml')
def locations():
    """
    Query locations
    :return:
    """
    # Read input [JSON] - Parameters can be either JSON or url parameters. Not both. [adapted for the paging]
    # request.args.get()
    input = request.get_json()
    # inputJson = readInputJSON()

    # Get dataset identification
    msg, status, pi_service_url, protocol = get_service_url(input)
    if status > 200:
        return jsonify(msg, status)

    # Query PiService
    pi = PiServiceDDL(pi_service_url, HOSTNAME_URL)
    content = pi.get_locations(input)

    return jsonify(content, 200)


# Dummy locations - /dummylocations
@app.route('/dummylocations', methods=['GET'])
def dummyLocations():
    """
    Dummy locations
    :return:
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, '../dummy_data/dummyLocations.json')) as f:
        content = json.load(f)
    return jsonify(content, 200)


@app.route('/timeseries', methods=['GET'])
def timeseries():
    """
    Timeseries query
    :return:
    """
    # Read input [JSON] - Parameters can be either JSON or url parameters. Not both.

    input = request.get_json()
    # inputJson = readInputJSON()

    # Get dataset identification
    msg, status, pi_service_url, protocol = get_service_url(input)
    if status > 200:
        return jsonify(msg, status)

    # Query PiService
    pi = PiServiceDDL(pi_service_url, HOSTNAME_URL)
    content = pi.get_timeseries(input)

    return jsonify(content, 200)


@app.route('/dummytimeseries', methods=['GET'])
def dummyTimeseries():
    """
    Dummy timeseries
    :return:
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, '../dummy_data/dummyTseries.json')) as f:
        content = json.load(f)
    return jsonify(content, 200)


# Datasets query / all
@app.route('/datasets', methods=['GET'])
def datasets():
    """
    Datasets
    :return:
    """
    # Return dummy file contents
    with open(os.path.join(APP_DIR, '../config_data/datasets.json')) as f:
        content = json.load(f)
    return jsonify(content, 200)


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