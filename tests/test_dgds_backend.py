import json
import unittest

from dgds_backend import app


class Dgds_backendTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()

    def test_index(self):
        rv = self.client.get('/')
        self.assertIn('Welcome to DGDS', rv.data.decode())

    def test_bad_datasetId(self):
        response = self.client.get('/locations?locationCode=diva_id__270&datasetId=wrongcode')
        print('bad_datasetId', response.data.decode())
        self.assertIn(response.data.decode('utf-8'), 'does not exist')

    def test_get_datasets(self):
        response = self.client.get('/datasets')

        # self.assertTrue(response.status_code, 200)
        result = json.loads(response.data.decode('utf-8'))

        expected_output = {
            "dataType": "timeseries",
            "description": "To be filled by Daniel",
            "id": "wl",
            "name": "Waterlevel",
            "timeSpan": "Live",
            "units": "m",
            "wmsUrl": "http://pl-tc012.xtr.deltares.nl:8080/FewsWebServices/wms?service=WMS&request=GetMap&version=1.3&layers=Water%20Level&styles=&format=image%2Fpng&transparent=true&crs=EPSG%3A3857&time=2019-04-24T10%3A00%3A00.000Z&uppercase=false&width=256&height=256&bbox={bbox-epsg-3857}"
        }
        self.assertIn(expected_output, result["Flooding"].get("datasets"))

    def test_get_locations(self):
        response = self.client.get('/locations?locationCode=diva_id__270&datasetId=wl')

        # self.assertTrue(response.status_code, 200)
        print('get_locations',response.data.decode('utf-8'))
        result = json.loads(response.data.decode('utf-8'))
        self.assertIn("geometry", result)

    def test_get_timeseries(self):
        input = {
            "datasetId": "wl",
            "locationCode": "diva_id__270",
            "startTime": "2019-03-22T00:00:00Z",
            "endTime": "2019-03-26T00:50:00Z",
            "observationTypeId": "H.simulated"
        }

        response = self.client.get('/timeseries?locationCode=diva_id__270&startTime=2019-03-22T00:00:00Z&endTime=2019-03-26T00:50:00Z&observationTypeId=H.simulated&datasetId=wl')
        # self.assertTrue(response.status_code, 200)
        print('get_timeseries', response.data.decode('utf-8'))
        result = json.loads(response.data.decode('utf-8'))
        self.assertIn("paging", result)



if __name__ == '__main__':
    unittest.main()
