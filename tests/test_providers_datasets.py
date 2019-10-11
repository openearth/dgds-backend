import json
import os
import unittest
from unittest.mock import patch

from dgds_backend import app

class datasetsTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()
        self.path = os.path.dirname(os.path.abspath(__file__))

    @patch("dgds_backend.app.requests.post")
    def test_get_hydroengine_url(self, mock_post):
        """
        Test response hydro-engine url request
        Check if correct key, values pairs are present in returned dict
        """
        respone = os.path.join(self.path, "datasets_respone/hydroengine_response.json")
        with open(respone) as json_file:
            hydroengine_resp = json.load(json_file)

        mock_post.return_value.status_code = 200
        mock_post.return_value.text = json.dumps(hydroengine_resp)

        id = "cc"
        layer_name = "currents"
        access_url = "https://sample-hydro-engine.appspot.com/get_glossis_data"
        parameters = {"bandName": ""}

        data = app.get_hydroengine_url(id, layer_name, access_url, parameters)
        expected_url = "https://earthengine.googleapis.com/map/"
        self.assertEqual(data["url"], expected_url)
        self.assertEqual(data["date"], "2018-06-01T12:00:00")
        self.assertEqual(data["min"], 0.0)
        self.assertEqual(data["max"], 1.0)
        self.assertIn("palette", data)

    @patch("dgds_backend.app.requests.get")
    def test_get_fews_url(self, mock_get):
        """
        Test response fews url request
        Check if correct key, values are present in returned dict
        """
        respone = os.path.join(self.path, "datasets_respone/fews_response.json")
        with open(respone) as json_file:
            fews_resp = json.load(json_file)

        mock_get.return_value.status_code = 200
        mock_get.return_value.text = json.dumps(fews_resp)

        id = "wd"
        url_access = "http://test-url.deltares.nl/"
        layer_name = "Significant Wave Height"
        parameters = {
            "urlTemplate": "http://test-url.deltares.nl/time=##TIME##&somethingelse"
        }

        data = app.get_fews_url(id, layer_name, url_access, parameters)

        expected_url = "http://test-url.deltares.nl/time=2019-08-01T13:00:00Z&somethingelse"
        self.assertEqual(data["url"], expected_url)
        self.assertEqual(data["dateFormat"], "YYYY-MM-DDTHH:mm:ssZ")
        self.assertEqual(data["date"], "2019-08-01T13:00:00Z")
