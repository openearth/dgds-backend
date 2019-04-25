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
        self.assertTrue(response.status_code, 400)

    def test_get_datasets(self):
        response = self.client.get('/datasets')

        # self.assertTrue(response.status_code, 200)
        result = json.loads(response.data)

        expected_output = {
            "id": "wl",
            "name": "Waterlevel",
            "description": "To be filled by Daniel",
            "timeSpan": "Live",
            "dataType": "timeseries",
            "units": "m"
        }
        self.assertIn(expected_output, result["Flooding"])

    def test_get_locations(self):
        response = self.client.get('/locations?locationCode=diva_id__270&datasetId=wl')

        # self.assertTrue(response.status_code, 200)
        result = json.loads(response.data)
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
        result = json.loads(response.data)
        self.assertIn("paging", result)


if __name__ == '__main__':
    unittest.main()
