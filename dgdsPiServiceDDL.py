import requests

class PiServiceDDL:
	def __init__(self, url, host):
		self.hostnameUrl = host
		self.piServiceUrl = url
		self.timeseriesUrl = url + '/timeseries'
		self.locationsUrl = url + '/locations'

	# Parameter transfer
	def passParam(self, parName, inData, parDict):
		if 'parName' in inData:
			parDict['parName'] = parDict['parName']

	# Update paging
	def updatePaging(self, url, urlLocal, respData):
		rr = respData
		if respData['paging']['prev'] != None:
			rr['paging']['prev'] = respData['paging']['prev'].replace(url, urlLocal)			
		if respData['paging']['next'] != None:			
			rr['paging']['next'] = respData['paging']['next'].replace(url, urlLocal)
		return rr

	# Get locations 
	def getLocations(self, data):
		# Build url parameters
		params = {}
		self.passParam('boundingBox', data, params)
		self.passParam('locationCode', data, params)
		self.passParam('page', data, params)
		
		# Query / Response
		resp = requests.get(url=self.locationsUrl, params=params)
		respData = resp.json()
		if 'paging' in respData:
			return self.updatePaging(self.locationsUrl, self.hostnameUrl+'/locations', respData)

		return resp

	# Get timeseries
	def getTimeSeries(self, data):
		# Build url parameters
		params = {}
		self.passParam('startTime', data, params)
		self.passParam('endTime', data, params)
		self.passParam('locationCode', data, params)
		self.passParam('page', data, params)

		# Query	/ Response	
		resp = requests.get(url=self.timeseriesUrl, params=params)
		if 'paging' in respData:
			return self.updatePaging(self.timeseriesUrl, self.hostnameUrl+'/timeseries', respData)

		return resp
