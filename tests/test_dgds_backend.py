import json
import unittest
import os
from unittest.mock import Mock, patch

from dgds_backend import app


class Dgds_backendTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_index(self):
        rv = self.client.get("/")
        self.assertIn("/swagger-ui", rv.data.decode())

    @patch("dgds_backend.app.requests.get")
    def test_get_fews_url(self, mock_get):
        mocked_fews_resp = """{
                    "title": "Spatial Display",
                    "layers": [{
                        "name": "Significant Wave Height",
                        "title": "Significant Wave Height",
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

        id = "wd"
        url_access = "http://test-url.deltares.nl/"
        layer_name = "Significant Wave Height"
        parameters = {
            "urlTemplate": "http://test-url.deltares.nl/time=##TIME##&somethingelse"
        }

        data = app.get_fews_url(
            id, layer_name, url_access, "featureinfourl", parameters
        )

        expected_url = (
            "http://test-url.deltares.nl/time=2019-08-01T13:00:00Z&somethingelse"
        )
        self.assertEqual(data["url"], expected_url)

    @patch("dgds_backend.app.requests.post")
    def test_get_hydroengine_url(self, mock_post):
        mocked_hydroengine_resp = """{
            "url": "https://earthengine.googleapis.com/map/",
            "dataset": "currents",
            "date": "2018-06-01T12:00:00",
            "min": 0.0,
            "max": 1.0,
            "palette": ["1d1b1a",  "621d62",  "7642a5", "7871d5", "76a4e5", "e6f1f1"]
        }"""

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = mocked_hydroengine_resp

        id = "cc"
        layer_name = "currents"
        access_url = "https://sample-hydro-engine.appspot.com/get_glossis_data"
        parameters = {"band": ""}

        data = app.get_hydroengine_url(
            id, layer_name, access_url, "featureinfourl", parameters
        )
        expected_url = "https://earthengine.googleapis.com/map/"
        self.assertEqual(data["url"], expected_url)
        self.assertEqual(data["date"], "2018-06-01T12:00:00")
        self.assertEqual(data["min"], 0.0)

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

        expected_data = json.loads(
            """{
            "bbox": [[-180.0, -90.0], [180.0, 90.0]],
            "scope": "global",
            "id": "wl",
            "name": "Water level",
            "layerOptions": [{
                "name": "1 year return period",
                "band": "water_level"
                },
                {
                "name": "2 year return period",
                "band": "water_level"
                }
            ],
			"locationIdField": "locationId",
            "pointData": "line",
            "rasterLayer": {
                "date": "2019-06-18T22:00:00",
                "dateFormat": "YYYY-MM-DDTHH:mm:ss",
                "featureInfoUrl": "https://hydro-engine.appspot.com/get_feature_info",
                "url": "https://earthengine.googleapis.com/map/"
            },
            "toolTip": "Water level, storm surge, tide and current forecasts from the Global Storm Surge Information System (GLOSSIS) at Deltares. This includes 10 day forecasts at hundreds of nearshore locations across the world. See https://www.deltares.nl/en/projects/global-storm-surge-information-system-glossis for more information.",
            "themes": ["fl", "cm"],
            "timeSpan": "Live",
            "units": "m",
            "vectorLayer": {
                "mapboxLayers": [{
                    "filterIds": ["H.simulated"],
                    "id": "GLOSSIS",
                    "onClick": {
                        "method": "showGraph"
                    },
                    "source": {
                        "type": "vector",
                        "url": "mapbox://global-data-viewer.6w19mbaw"
                    },
                    "source-layer": "pltc012flat",
                    "type": "circle"
                }]
            }
        }"""
        )

        response = self.client.get("/datasets")
        result = json.loads(response.data)
        self.assertIn(expected_data, result["datasets"])

    @patch("dgds_backend.app.requests.post")
    def test_get_datasets_with_min_max(self, mock_post):
        mock_post.return_value = Mock()
        mocked_hydroengine_resp = """{
            "url": "https://earthengine.googleapis.com/map/",
            "dataset": "currents",
            "date": "2018-06-01T12:00:00",
            "imageId": "image_id_sample",
            "min": 10,
            "max": 20,
            "palette": ["1d1b1a",  "621d62",  "7642a5", "7871d5", "76a4e5", "e6f1f1"]
        }"""

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = mocked_hydroengine_resp

        response = self.client.get("/datasets/cc/image_id_sample?min=10&max=20")
        result = json.loads(response.data)
        self.assertEqual(result["min"], 10)

    @patch("dgds_backend.app.requests.get")
    def test_get_fews_timeseries(self, mock_get):
        # Test FEWS PI service
        filename = os.path.join(
            os.path.dirname(__file__), "../dgds_backend/dummy_data/dummyTseries.json"
        )
        with open(filename, "r") as f:
            mocked_fews_resp = json.load(f)
        mock_get.return_value = Mock()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mocked_fews_resp
        response = self.client.get(
            "/timeseries?locationId=diva_id__270&startTime=2019-03-22T00:00:00Z&endTime=2019-03-26T00:50:00Z&observationTypeId=H.simulated&datasetId=wl"
        )
        result = json.loads(response.data.decode("utf-8"))
        self.assertIn("events", result["results"][1])

    def test_get_shoreline_timeseries(self):
        # Test get timeseries from shoreline service
        response = self.client.get("/timeseries?locationId=BOX_120_000_32&datasetId=sm")
        result = json.loads(response.data)
        self.assertIn("events", result["results"][0])


if __name__ == "__main__":
    unittest.main()
