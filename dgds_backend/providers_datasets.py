import logging
import json
import requests
from os.path import dirname, realpath
from pathlib import Path

from dgds_backend import error_handler


# Load general settings
APP_DIR = Path(dirname(realpath(__file__)))

# Dataset settings
try:
    DATASETS = {}
    fnameDatasets = Path(APP_DIR / "config_data" / "datasets.json")
    fnameAccess = Path(APP_DIR / "config_data" / "datasets_access.json")
    with open(str(fnameDatasets), "r") as fd:
        DATASETS["info"] = json.load(fd)  # str for python 3.4, works without on 3.6+
    with open(str(fnameAccess), "r") as fa:
        DATASETS["access"] = json.load(fa)  # str for python 3.4, works without on 3.6+

except FileNotFoundError as e:
    logging.error("Missing datasets.json (%s) datasets_access.json (%s), please check your deployment settings",
                  fnameDatasets, fnameAccess)
    exit(-1)  # vital config needed


# Get the associated service url to a dataset inside the params dict
def get_service_url(datasetId, serviceType):
    """
    Get dataset identification
    :param params:
    :return:
    """

    service_url_data = DATASETS["access"][datasetId][serviceType]

    return service_url_data


def get_hydroengine_url(id, layer_name, access_url, feature_url, parameters, image_id=None):
    """
    Get hydroengine url and other info
    :param id: dataset id, as defined in datasets.json and datasets_access.json
    :return: url
    """

    data = {
        "featureInfoUrl": feature_url
    }

    post_data = {
        "dataset": layer_name,
        "imageId": image_id
    }
    post_data.update(parameters)
    resp = requests.post(url=access_url, json=post_data)

    if resp.status_code == 200:
        data.update(json.loads(resp.text))
        # Remove unnecessary keys
        [data.pop(key, None) for key in ["dataset", "token"]]
        if "date" in data:
            data["dateFormat"] = "YYYY-MM-DDTHH:mm:ss"

    else:
        logging.error("Dataset id {} not reached. Error {}".format(id, resp.status_code))

    return data


def get_fews_url(id, layer_name, access_url, feature_url, parameters):
    """
    Get FEWS Pi WMS url by filling in template with latest time
    :param id: dataset id, as defined in datasets.json and datasets_access.json
    :param url_template: template of url to adjust
    :return: url
    """
    data = {
        "featureInfoUrl": feature_url
    }

    resp = requests.get(url=access_url)

    if resp.status_code == 200:
        fews_data = json.loads(resp.text)

        # ignore layers in hydroengine
        for layer in fews_data["layers"]:
            if layer["name"] == layer_name:
                url_template = parameters["urlTemplate"]
                times = layer["times"]
                data["date"] = times[-1]
                data["url"] = url_template.replace("##TIME##", times[-1])
                data["dateFormat"] = "YYYY-MM-DDTHH:mm:ssZ"
            else:
                continue
    else:
        logging.error("Dataset id {} not reached. Error {}".format(id, resp.status_code))

    return data
