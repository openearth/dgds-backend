# FLASK
from flask import Flask
from flask import request, jsonify
from flask_cors import CORS

# FLASK app
application = Flask(__name__)
CORS(application)

# JSON input to dict
def readInputJSON():
	# Inputs
	jsonData = request.get_json()
	return jsonData

# dict to JSON
def prepareOutputJSON(content, status):
	return jsonify(content), status

# Application root - /
@application.route('/', methods=['GET'])
def slash():
	inputJ = readInputJSON()
	content = {'error': 'nothing to see here, perhaps looking for /services or /tseries?'}
	return prepareOutputJSON(content, 200)

# Services list - /services
@application.route('/services', methods=['GET'])
def services():
	inputJ = readInputJSON()
	content = {'services': 'dummy'}
	return prepareOutputJSON(content, 200)

# Time-series query - /tseries
@application.route('/tseries', methods=['GET'])
def tseries():
	inputJ = readInputJSON()
	content = {'tseries': 'dummy'}
	return prepareOutputJSON(content, 200)

# Main
if __name__ == "__main__":
	application.run(host='0.0.0.0', debug=True)    