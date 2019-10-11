import json
import unittest
import os
from unittest.mock import Mock, patch

from dgds_backend import app


class PiServiceDDLTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()

        observation_type_id = "cc"
        url = "dgds.example.com"
        host = "host"
        Pirequest = app.PiServiceDDL(observation_type_id, url, host)


    @patch("dgds_backend.app.requests.get")
    @patch("dgds_backend.app.requests.post")
    def test_get_datasets_url(self, mock_post, mock_get):
        mock_get.return_value = Mock()
        mock_post.return_value = Mock()
        mocked_hydroengine_resp = """{
            "dataset": "waterlevel",
            "date": "2019-06-18T22:00:00",
            "url": "https://earthengine.googleapis.com/map/"
        }"""

        mocked_fews_resp = """{
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
        }"""

        mock_get.return_value.status_code = 200
        mock_get.return_value.text = mocked_fews_resp

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = mocked_hydroengine_resp

        expected_data = json.loads("""{
            "id": "wl",
            "name": "Water level",
			"locationIdField": "locationId",
            "pointData": "line",
            "rasterLayer": {
                "date": "2019-06-18T22:00:00",
                "dateFormat": "YYYY-MM-DDTHH:mm:ss",
                "url": "https://earthengine.googleapis.com/map/"
            },
            "themes": ["fl", "cm"],
            "timeSpan": "Live",
            "units": "m",
            "vectorLayer": {
                "mapboxLayers": [{
                    "filterIds": ["H.simulated"],
                    "id": "GLOSSIS",
                    "source": {
                        "type": "vector",
                        "url": "mapbox://global-data-viewer.6w19mbaw"
                    },
                    "source-layer": "pltc012flat",
                    "type": "circle"
                }]
            }
        }""")

        response = self.client.get("/datasets")
        result = json.loads(response.data)
        self.assertIn(expected_data, result["datasets"])

    @patch("dgds_backend.app.requests.get")
    def test_get_fews_timeseries(self, mock_get):
        # Test FEWS PI service
        filename = os.path.join(os.path.dirname(__file__), "../dgds_backend/dummy_data/dummyTseries.json")
        with open(filename, "r") as f:
            mocked_fews_resp = json.load(f)
        mock_get.return_value = Mock()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mocked_fews_resp
        response = self.client.get(
            "/timeseries?locationId=diva_id__270&startTime=2019-03-22T00:00:00Z&endTime=2019-03-26T00:50:00Z&observationTypeId=H.simulated&datasetId=wl")
        result = json.loads(response.data.decode("utf-8"))
        self.assertIn("events", result["results"][1])

    def test_get_shoreline_timeseries(self):
        # Test get timeseries from shoreline service
        response = self.client.get(
            "/timeseries?locationId=BOX_120_000_32&datasetId=sm")
        result = json.loads(response.data)
        self.assertIn("events", result["results"][0])


if __name__ == "__main__":
    unittest.main()
