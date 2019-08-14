import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from jinja2 import Template


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
    template_file = Path(filepath / "templates" / "dd_timeseries_template.json")
    with open(template_file, "r") as f:
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

    return template.render(dataset=dataset, transect=transect)


def dd_shoreline(url, transect_id, dataset_name, dataset_id):
    box, section = transect_id.split("_")
    url = url.format(**{"box": box, "section": section})

    response = requests.get(url)
    featurecollection = response.json()

    # Filter FeatureCollection
    transect = None
    for feature in featurecollection.get("features", []):
        if transect_id in feature.get("properties", {}).get("transect_id", ""):
            transect = feature

    if transect is None:
        return {}

    # Transform transect
    dd_transect = transform_dd(transect, dataset_name, dataset_id)

    return dd_transect
