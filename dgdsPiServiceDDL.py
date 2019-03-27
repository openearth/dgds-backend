import requests

class PiServiceDDL:
	def __init__(self, url, host):
		self.hostnameUrl = host
		self.piServiceUrl = url
		self.timeseriesUrl = url + '/timeseries'
		self.locationsUrl = url + '/locations'

	# Update paging
	def updatePaging(self, url, urlLocal, respData):
		rr = respData
		if respData['paging']['prev'] != None:
			rr['paging']['prev'] = respData['paging']['prev'].replace(url, urlLocal)			
		if respData['paging']['next'] != None:			
			rr['paging']['next'] = respData['paging']['next'].replace(url, urlLocal)
		return rr

	# Make actual request to the PiServiceDDL
	def makeRequest(self, data, ddlUrl, urlPath):
		# Query / Response
		resp = requests.get(url=ddlUrl, params=data)
		if resp.status_code == 200:
			respData = resp.json()
			if 'paging' in respData:
				respData = self.updatePaging(self.locationsUrl, self.hostnameUrl+'/'+urlPath, respData)
		else:
			respData = {'error': 'Requesting data from the DD-API/locations '}
		return respData

	# Get locations 
	def getLocations(self, data):
		# Query / Response
		return self.makeRequest(data, self.locationsUrl, 'locations')

	# Get timeseries
	def getTimeSeries(self, data):
		# Query	/ Response
		return self.makeRequest(data, self.timeseriesUrl, 'timeseries')

