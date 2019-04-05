import os
import json

# Application directory
APP_DIR = os.path.dirname(os.path.realpath(__file__))

# Endpoints test
from dgdsPiServiceDDL import *

def checkLocation(resp, locCode):
    loc = resp.json()
    return loc['properties']['locationId'] == locCode

def checkTimeseries(resp, locCode):
    ts = resp.json()
    return ts['results'][0]['location']['properties']['locationId'] == locCode

def checkDatasets(resp):
    ts = resp.json()
    ds = {}
    with open(os.path.join(APP_DIR, 'configData/datasets.json')) as fd:
        ds = json.load(fd)
    return sorted(ts.items()) == sorted(ds.items())

def checkPaging(url):
    # Recursive end
    if url == None:
        return True
    # Recursive crawl
    else:
        resp = requests.get(url)
        if resp.status_code == 200:
            jsonData = resp.json()
            return checkPaging(jsonData['paging']['next'])

def checkError(resp):
    return resp.status_code > 200

# Tests for each endpoint
if __name__ == "__main__":

    # Url from command-line params
    url = 'http://localhost:5000'

    # Test 0 - one given location
    t0 = {
        "datasetId": "wl",
        "locationCode": "diva_id__270"
    }
    tr0 = checkLocation(requests.get(url+'/locations', params=t0), t0['locationCode'])
    print('test0:{}'.format(tr0))

    # Test 1 - Given timeseries
    t1 = {
        "datasetId": "wl",
        "locationCode": "diva_id__270",
        "startTime": "2019-03-22T00:00:00Z",
        "endTime": "2019-03-26T00:50:00Z",
        "observationTypeId": "H.simulated"
    }
    tr1 = checkTimeseries(requests.get(url + '/timeseries', params=t1), t1['locationCode'])
    print('test1:{}'.format(tr1))

    # Test 2 - All datasets
    tr2 = checkDatasets(requests.get(url + '/datasets'))
    print('test2:{}'.format(tr2))

    # Test 3 - Error check datasetId missing
    t3 = {
        "locationCode": "diva_id__270"
    }
    tr3 = checkError(requests.get(url+'/locations', params=t3))
    print('test3:{}'.format(tr3))

    # Test 4 - Given timeseries
    t4 = {
        "locationCode": "diva_id__270",
        "startTime": "2019-03-22T00:00:00Z",
        "endTime": "2019-03-26T00:50:00Z",
        "observationTypeId": "H.simulated"
    }
    tr4 = checkError(requests.get(url+'/locations', params=t4))
    print('test4:{}'.format(tr4))

    # Test 5 - Paging test [small bounding box, 10 pages]
    tr5 = checkPaging(url+'/locations?boundingBox=4.123456,52.123456,10.123456,55.123456&datasetId=wl')
    print('test5:{}'.format(tr5))

    # Total
    print('------------')
    print('TOTAL:{}'.format(tr0 & tr1 & tr2 & tr3 & tr4 & tr5))
