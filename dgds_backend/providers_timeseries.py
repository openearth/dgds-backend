import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from requests.exceptions import RequestException
import json
from jinja2 import Template
import logging

from dgds_backend import error_handler


class PiServiceDDL:
    def __init__(self, observation_type_id, url, host):
        self.observation_type_id = observation_type_id
        self.hostname_url = host
        self.pi_service_url = url
        self.timeseries_url = url + "/timeseries"
        self.locations_url = url + "/locations"

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
        if resp_data["paging"]["prev"] is not None:
            rr["paging"]["prev"] = resp_data["paging"]["prev"].replace(url, url_local) + "&datasetId=" + dataset_id
        if resp_data["paging"]["next"] is not None:
            rr["paging"]["next"] = resp_data["paging"]["next"].replace(url, url_local) + "&datasetId=" + dataset_id
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
        dataset_id = data.pop("datasetId", None)
        if url_path == "timeseries":
            data["observationTypeId"] = self.observation_type_id

        # replace locationId with locationCode
        location_id = data.pop("locationId", None)
        data["locationCode"] = location_id

        # Query / Response
        try:
            resp = requests.get(url=ddl_url, params=data)
            if resp.status_code != 200:
                raise(RequestException("Failed request."))

        except RequestException as e:
            msg = "Failed to fetch from the DD-API/locations"
            raise error_handler.InvalidUsage(msg)

        logging.info(data, ddl_url, url_path, resp)
        resp_data = resp.json()
        if "paging" in resp_data:
            resp_data = self.update_paging(ddl_url, self.hostname_url + url_path, resp_data, dataset_id)

        return resp_data

    def get_locations(self, data):
        """
        Get locations
        :param data:
        :return:
        """
        # Query / Response
        return self.make_request(data, self.locations_url, "locations")

    # Get timeseries
    def get_timeseries(self, data):
        """
        Get timeseries
        :param data:
        :return:
        """
        # Query	/ Response
        return self.make_request(data, self.timeseries_url, "timeseries")



def transform_dd(feature, dataset_name, dataset_id):
    """
    Transform a shoreline transect feature into Digital Delta format, from template
    :param feature: json of transect feature data
    :param dataset_name: name of dataset
    :param dataset_id: id of dataset
    :return: rendered template, JSON of transect timeseries info in Digital Delta format
    """
    # Dates for Shoreline monitor are defined as days since 01-01-1984.
    start_time = datetime(1984, 1, 1, 00, 00, 00)
    dataset = {"name": dataset_name, "id": dataset_id}

    # Load template
    filepath = Path(os.path.dirname(os.path.realpath(__file__)))
    template_file = Path(filepath / "templates" / "dd_timeseries_template.json.j2")
    with open(str(template_file), "r") as f:
        template_json = f.read()

    template = Template(template_json)

    # Transform timeseries data
    dt = feature["properties"]["dt"]
    dates = [start_time + timedelta(days=(x * 365)) for x in dt]
    points = feature["properties"]["distances"]

    # Build events list from timeseries
    events_list = []
    for date, point in zip(dates, points):
        event = {}
        event["timeStamp"] = date.strftime("%Y-%m-%dT%H:%M:%SZ")
        event["value"] = point
        events_list.append(event)

    # Build dictionary to send to template
    transect = {}
    transect["type"] = feature["type"]
    transect["geometry"] = feature["geometry"]
    transect["properties"] = {}
    transect["properties"]["locationId"] = feature["properties"]["transect_id"]
    transect["properties"]["countryName"] = feature["properties"]["country_name"]
    transect["properties"]["continent"] = feature["properties"]["continent"]
    transect["properties"]["flagSandy"] = feature["properties"]["flag_sandy"]
    transect["properties"]["changeRate"] = feature["properties"]["change_rate"]
    transect["properties"]["changeRateUnc"] = feature["properties"]["change_rate_unc"]
    transect["startTime"] = dates[0].strftime("%Y-%m-%dT%H:%M:%SZ")
    transect["endTime"] = dates[-1].strftime("%Y-%m-%dT%H:%M:%SZ")
    transect["events"] = events_list

    rendered = template.render(dataset=dataset, transect=transect).replace("'", '"')
    dic = json.loads(rendered)
    return dic


def dd_shoreline(url, transect_id, dataset_name, dataset_id):
    _, box, section, number = transect_id.split("_")
    url = url.format(**{"box": box, "section": section})

    response = requests.get(url)
    featurecollection = response.json()

    # Filter FeatureCollection
    transect = None
    for feature in featurecollection.get("features", []):
        if feature.get("properties", {}).get("transect_id", transect_id) == transect_id:
            transect = feature

    if transect is None:
        return {}

    # Transform transect
    dd_transect = transform_dd(transect, dataset_name, dataset_id)

    return dd_transect
