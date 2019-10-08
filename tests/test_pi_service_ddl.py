import unittest

from dgds_backend import app
from dgds_backend.providers_timeseries import PiServiceDDL


class Dgds_backendTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()
        # self.client.HOSTNAME
        self.url = "http://pl-tc012.xtr.deltares.nl:8080/FewsWebServices/rest/digitaledelta/2.0"
        self.pi = PiServiceDDL('H.simulated', self.url, self.client)

    def test_get_locations(self):
        data = {
            "datasetId": "wl",
            "locationCode": "diva_id__270"
        }
        # self.pi.get_locations(data)
        pass

    def test_update_paging(self):
        # self.pi.update_paging(self.url, self.client, )
        pass
