import json
import unittest

from dgds_backend import app
from unittest.mock import patch


class Dgds_backendTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()

    def test_index(self):
        rv = self.client.get('/')
        self.assertIn('Welcome to DGDS', rv.data.decode())

    @patch('dgds_backend.app.requests.get')
    def test_get_wms_url(self, mock_get):

        mocked_fews_resp = '''{
            "title": "Spatial Display",
            "layers": [{
                "name": "Wind NOAA GFS",
                "title": "Wind NOAA GFS",
                "groupName": "GLOSSIS",
                "times": ["2019-08-01T10:00:00Z", "2019-08-01T13:00:00Z"]
            }, {
                "name": "Water Level",
                "title": "Water Level",
                "groupName": "D3D-FM gtsm",
                "times": ["2019-08-01T12:00:00Z", "2019-08-01T13:00:00Z"]
            }, {
                "name": "Current 2DH",
                "title": "Current 2DH",
                "groupName": "D3D-FM gtsm",
                "times": ["2019-08-01T12:00:00Z", "2019-08-01T13:00:00Z"]
            }]
        }'''

        mock_get.return_value.status_code = 200
        mock_get.return_value.text = mocked_fews_resp

        id = "wd"
        url_template = "http://pl-tc012.xtr.deltares.nl:8080/FewsWebServices/wms?service=WMS&request=GetMap&version=1.3&layers=Wind%20NOAA%20GFS&styles=&format=image%2Fpng&transparent=true&crs=EPSG%3A3857&time=##TIME##&uppercase=false&width=256&height=256&bbox={bbox-epsg-3857}"

        url = app.get_wms_url(id, url_template)

        expected_url = "http://pl-tc012.xtr.deltares.nl:8080/FewsWebServices/wms?service=WMS&request=GetMap&version=1.3&layers=Wind%20NOAA%20GFS&styles=&format=image%2Fpng&transparent=true&crs=EPSG%3A3857&time=2019-08-01T13:00:00Z&uppercase=false&width=256&height=256&bbox={bbox-epsg-3857}"
        self.assertEqual(url, expected_url)

    @patch('dgds_backend.app.requests.post')
    def test_get_hydroengine_url(self, mock_post):

        mocked_hydroengine_response = '''{
            "mapid": "1311df60b987b59a9aefc5ee500dd17c",
            "token": "82604cf0c22d23dfcdc44f6838fb014c",
            "url": "https://earthengine.googleapis.com/map/1311df60b987b59a9aefc5ee500dd17c/{z}/{x}/{y}?token=82604cf0c22d23dfcdc44f6838fb014c",
            "dataset": "currents"
        }'''

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = mocked_hydroengine_response

        id = "cc"

        url = app.get_hydroengine_url(id)

        expected_url = "https://earthengine.googleapis.com/map/1311df60b987b59a9aefc5ee500dd17c/{z}/{x}/{y}?token=82604cf0c22d23dfcdc44f6838fb014c"
        self.assertEqual(url, expected_url)

    def test_get_timeseries(self):
        response = self.client.get(
            '/timeseries?locationCode=diva_id__270&startTime=2019-03-22T00:00:00Z&endTime=2019-03-26T00:50:00Z&observationTypeId=H.simulated&datasetId=wl')
        result = json.loads(response.data.decode('utf-8'))
        self.assertIn("paging", result)


if __name__ == '__main__':
    unittest.main()
