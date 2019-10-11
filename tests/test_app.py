import unittest

from dgds_backend import app

class EndpointsTestCase(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()

    def test_index(self):
        rv = self.client.get("/")
        self.assertIn("/swagger-ui", rv.data.decode())