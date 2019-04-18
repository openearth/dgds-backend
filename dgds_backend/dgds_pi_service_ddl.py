import requests

from dgds_backend import error_handler


class PiServiceDDL:
    def __init__(self, url, host):
        self.hostname_url = host
        self.pi_service_url = url
        self.timeseries_url = url + '/timeseries'
        self.locations_url = url + '/locations'

    def update_paging(self, url, url_local, resp_data, dataset_id):
        """
        Update paging
        :param url:
        :param url_local:
        :param resp_data:
        :param dataset_id:
        :return:
        """
        rr = resp_data
        if resp_data['paging']['prev'] != None:
            rr['paging']['prev'] = resp_data['paging']['prev'].replace(url, url_local) + '&dataset_id=' + dataset_id
        if resp_data['paging']['next'] != None:
            rr['paging']['next'] = resp_data['paging']['next'].replace(url, url_local) + '&dataset_id=' + dataset_id
        return rr

    def make_request(self, data, ddl_url, url_path):
        """
        Make request to the PiServiceDDL
        :param data:
        :param ddl_url:
        :param url_path:
        :return:
        """
        # dataset_id not needed
        dataset_id = data.pop('dataset_id', None)
        # Query / Response
        resp = requests.get(url=ddl_url, params=data)
        print(data, ddl_url, url_path, resp)
        if resp.status_code == 200:
            resp_data = resp.json()
            if 'paging' in resp_data:
                resp_data = self.update_paging(ddl_url, self.hostname_url + '/' + url_path, resp_data, dataset_id)
        else:
            msg = 'Failed to fetch from the DD-API/locations'
            raise error_handler.InvalidUsage(msg)

        return resp_data

    def get_locations(self, data):
        """
        Get locations
        :param data:
        :return:
        """
        # Query / Response
        return self.make_request(data, self.locations_url, 'locations')

    # Get timeseries
    def get_timeseries(self, data):
        """
        Get timeseries
        :param data:
        :return:
        """
        # Query	/ Response
        return self.make_request(data, self.timeseries_url, 'timeseries')
