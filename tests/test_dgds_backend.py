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
        input = {
            "datasetId": "wrongcode",
            "locationCode": "diva_id__270"
        }

        response = self.client.get('/locations', data=json.dumps(input),
                                   content_type='application/json')
        self.assertTrue(response.status_code, 400)

    def test_get_datasets(self):
        response = self.client.get('/datasets',
                                   content_type='application/json')

        self.assertTrue(response.status_code, 200)
        result = json.loads(response.data)

        expected_output = {
            "id": "wl",
            "name": "Waterlevel",
            "description": "To be filled by Daniel",
            "timeSpan": "Live",
            "dataType": "timeseries",
            "units": "m"
        }
        self.assertIn(expected_output, result[0].get("Flooding"))

    def test_get_locations(self):
        input = {
            "datasetId": "wl",
            "locationCode": "diva_id__270"
        }

        response = self.client.get('/locations', data=json.dumps(input),
                                   content_type='application/json')

        self.assertTrue(response.status_code, 200)

        result = json.loads(response.data)
        self.assertEqual(result, input)

    def test_get_timeseries(self):
        input = {
            "datasetId": "wl",
            "locationCode": "diva_id__270",
            "startTime": "2019-03-22T00:00:00Z",
            "endTime": "2019-03-26T00:50:00Z",
            "observationTypeId": "H.simulated"
        }

        response = self.client.get('/timeseries', data=json.dumps(input),
                                   content_type='application/json')

        self.assertTrue(response.status_code, 200)

        result = json.loads(response.data)

        self.assertIn("locationCode", result)


if __name__ == '__main__':
    unittest.main()
