# LIBS
import json
import os
import configparser

# FLASK
from flask import Flask
from flask import request, jsonify
from flask_cors import CORS

# PROJECT
from dgdsPiServiceDDL import *

# FLASK app
application = Flask(__name__)
CORS(application)
APP_DIR = os.path.dirname(os.path.realpath(__file__))

# --- FLASK app settings --- #
try:
	CONFIG = configparser.ConfigParser()
	CONFIG.read(os.path.join(APP_DIR, 'config.ini'))
	API_ROOT = CONFIG['server']['apiroot']
	HOSTNAME_URL = 'http://{host}:{port}/{apiroot}'.format(
		prot=CONFIG['server']['protocol'],
		host=CONFIG['server']['hostname'],
		port=CONFIG['server']['port'],
		apiroot=CONFIG['server']['apiroot'])

except Exception as e:
	print('Missing config.ini, please check your deployment settings')
	exit(-1)  # vital config needed

# --- Dataset settings --- #
try:
	DATASETS = {}
	with open(os.path.join(APP_DIR, 'configData/datasets.json')) as fd:
		DATASETS['info'] = json.load(fd)
	with open(os.path.join(APP_DIR, 'configData/datasetsAccess.json')) as fa:
		DATASETS['access'] = json.load(fa)
except Exception as e:
	print('Missing datasets.json/datasetsAccess.json, please check your deployment settings')
	exit(-1) # vital config needed

# Get the associated service url to a dataset inside the params dict
def getServiceUrl(params):
	# Get dataset identification
	serviceUrl = None
	protocol = None
	status = 200
	msg = {}
	try:
		if 'datasetId' in params:
			serviceUrl = DATASETS['access'][params['datasetId']]['urlData']
			protocol = DATASETS['access'][params['datasetId']]['protocolData']
		else:
			status = 400
			msg = {'error': 'No datasetId specified in the request'}
	except Exception as e:
		status = 400
		msg = {'error': 'The provided dataset does not exist'}

	return msg, status, serviceUrl, protocol

# JSON input to dict
def readInputJSON():
	# Inputs (Preferably JSON input, also takes url params as JSON dict)
	jsonData = request.get_json()
	if jsonData is None:
		jsonData = request.args.to_dict(flat=True)
	return jsonData

# dict to JSON
def prepareOutputJSON(content, status):
	return jsonify(content), status

# Application root - /
@application.route('/{}'.format(API_ROOT), methods=['GET'])
def slash():	
	content = {'error': 'nothing to see here, perhaps looking for /{r}/datasets, /{r}/timeseries or /{r}/locations?'.format(r=API_ROOT)}
	return prepareOutputJSON(content, 200)

# Query locations - /locations
@application.route('/{}/locations'.format(API_ROOT), methods=['GET'])
def locations():
	# Read input [JSON] - Parameters can be either JSON or url parameters. Not both. [adapted for the paging]
	inputJson = readInputJSON()

	# Get dataset identification
	msg, status, piServiceUrl, protocol = getServiceUrl(inputJson)
	if status > 200:
		return prepareOutputJSON(msg, status)

	# Query PiService
	try:
		pi = PiServiceDDL(piServiceUrl, HOSTNAME_URL)
		content = pi.getLocations(inputJson)
	except Exception as e:
		return prepareOutputJSON('FEWS service unavailable', 500)

	return prepareOutputJSON(content, 200)

# Dummy locations - /dummylocations
@application.route('/{}/dummylocations'.format(API_ROOT), methods=['GET'])
def dummyLocations():
	# Return dummy file contents
	with open(os.path.join(APP_DIR, './dummyData/dummyLocations.json')) as f:
		content = json.load(f)
	return prepareOutputJSON(content, 200)

# Time-series query - /tseries
@application.route('/{}/timeseries'.format(API_ROOT), methods=['GET'])
def timeseries():
	# Read input [JSON] - Parameters can be either JSON or url parameters. Not both.
	inputJson = readInputJSON()

	# Get dataset identification
	msg, status, piServiceUrl, protocol = getServiceUrl(inputJson)
	if status > 200:
		return prepareOutputJSON(msg, status)

	# Query PiService
	try:
		pi = PiServiceDDL(piServiceUrl, HOSTNAME_URL)
		content = pi.getTimeSeries(inputJson)
	except Exception as e:
		return prepareOutputJSON('FEWS service unavailable', 500)

	return prepareOutputJSON(content, 200)

# Dummy timeseries - /dummytimeseries
@application.route('/{}/dummytimeseries'.format(API_ROOT), methods=['GET'])
def dummyTimeseries():
	# Return dummy file contents
	with open(os.path.join(APP_DIR, './dummyData/dummyTseries.json')) as f:
		content = json.load(f)
	return prepareOutputJSON(content, 200)

# Datasets query / all
@application.route('/{}/datasets'.format(API_ROOT), methods=['GET'])
def datasets():
	# Return dummy file contents
	with open(os.path.join(APP_DIR, './configData/datasets.json')) as f:
		content = json.load(f)
	return prepareOutputJSON(content, 200)

# Main
if __name__ == "__main__":
	application.run(host='0.0.0.0', debug=True)    