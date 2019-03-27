import json

# Endpoints test
from dgdsPiServiceDDL import *

# PiSerivceUrl-DDL: for now hardcoded. Config file? Services?
PISERVICE_URL = 'http://pl-tc012.xtr.deltares.nl:8080/FewsWebServices/rest/digitaledelta/2.0'

# Hostname URL: Also hard-coded for now, sorry
HOSTNAME_URL = 'http://localhost:5000'

def testLocations(inData):
    with open('./dummyData/dummyLocations.json') as f:
        dd = json.load(f)
    pi = PiServiceDDL(PISERVICE_URL, HOSTNAME_URL)
    piRes = pi.getLocations(inData)

    # Exactly one location requested
    return dd['properties']['locationId'] == piRes['properties']['locationId'] and len(dd) == len(piRes)

def testTimeSeries(inData):
    with open('./dummyData/dummyTseries.json') as f:
        dd = json.load(f)
    pi = PiServiceDDL(PISERVICE_URL, HOSTNAME_URL)
    piRes = pi.getTimeSeries(inData)

    # Exact same event
    return dd['results'][1]['events'] == piRes['results'][1]['events'] and len(dd) == len(piRes)

# Tests for each endpoint
if __name__ == "__main__":
    print(testLocations({
        "locationCode": "diva_id__270"
    }))
    print(testTimeSeries({
        "locationCode": "diva_id__270",
        "startTime": "2019-03-22T00:00:00Z",
        "endTime": "2019-03-26T00:50:00Z",
        "observationTypeId": "H.simulated"
    }))