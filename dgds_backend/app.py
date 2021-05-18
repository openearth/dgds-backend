from copy import deepcopy
import json
import logging
from pathlib import Path
import os
from copy import copy
from datetime import datetime
import requests
import pystac

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    request,
    send_from_directory,
    url_for,
)
from flask_apispec import marshal_with, use_kwargs
from flask_apispec.extension import FlaskApiSpec
from flask_caching import Cache
from flask_cors import CORS
from marshmallow import fields, validate
from pystac import Link

from dgds_backend import error_handler
from dgds_backend.providers_datasets import (
    DATASETS,
    STAC_GEE,
    stacdir,
    get_fews_url,
    get_google_storage_url,
    get_hydroengine_url,
    get_service_url,
)
from dgds_backend.providers_timeseries import PiServiceDDL, dd_shoreline
from dgds_backend.schemas import DatasetSchema, TimeSerieSchema


app = Flask(__name__)
CORS(app)
cache = Cache(app, config={"CACHE_TYPE": "simple"})
app.config.update(
    {
        "APISPEC_SPEC": APISpec(
            title="DGDS backend",
            openapi_version="2.0.0",
            version="1.0",
            plugins=[MarshmallowPlugin()],
        ),
        "APISPEC_SWAGGER_URL": "/swagger/",
    }
)
docs = FlaskApiSpec(app)

# Configuration load
app.config.from_object("dgds_backend.default_settings")
try:
    app.config.from_envvar("DGDS_BACKEND_SETTINGS")
except (RuntimeError, FileNotFoundError) as e:
    print(
        "Could not load config from environment variables"
    )  # logging not set yet [could not read config]

# only catch error if we're not in debug mode
if not app.debug:
    app.register_blueprint(error_handler.error_handler)

# Logging setup
if not app.debug:
    from logging.handlers import TimedRotatingFileHandler

    # https://docs.python.org/3.6/library/logging.handlers.html#timedrotatingfilehandler
    file_handler = TimedRotatingFileHandler(
        os.path.join(app.config["LOG_DIR"], "dgds_backend.log"), "midnight"
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("<%(asctime)s> <%(levelname)s> %(message)s")
    )
    app.logger.addHandler(file_handler)


@app.route("/locations", methods=["GET", "POST"])
@use_kwargs(
    {
        "datasetId": fields.Str(
            required=True, validate=validate.OneOf(DATASETS["access"].keys())
        )
    }
)
def locations(**input):
    """
    Query locations
    """

    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = (
        service_url_data["url"],
        service_url_data["name"],
        service_url_data["protocol"],
        service_url_data["parameters"],
    )

    # Query PiService
    pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
    content = pi.get_locations(input)

    return jsonify(content)


@app.route("/timeseries", methods=["GET", "POST"])
@use_kwargs(
    {
        "datasetId": fields.Str(
            required=True, validate=validate.OneOf(DATASETS["access"].keys())
        ),
        "locationId": fields.Str(required=True),
        "startTime": fields.Str(),
        "endTime": fields.Str(),
    }
)
@marshal_with(TimeSerieSchema(many=True))
def timeseries(**input):
    """
    Timeseries query
    """
    # Get dataset identification
    service_url_data = get_service_url(input["datasetId"], "dataService")
    data_url, observation_type_id, protocol = (
        service_url_data["url"],
        service_url_data["name"],
        service_url_data["protocol"],
    )

    # Query PiService
    if protocol == "dd-api":
        pi = PiServiceDDL(observation_type_id, data_url, request.url_root)
        content = pi.get_timeseries(input)

    # Specific endpoint for DD like shoreline data
    elif protocol == "dd-api-shoreline":
        transect = input.get("locationId", None)
        content = dd_shoreline(
            data_url, transect, observation_type_id, input["datasetId"]
        )

    # Specific endpoint for static images
    elif protocol == "staticimage":
        content = data_url.format(**input)

    else:
        error = "Unknown protocol in configuration."
        raise HTTPException(error)
        logging.error(error)

    return jsonify(content)


@app.route("/datasets", methods=["GET"])
# cache this request so it returns the same result for 6 hours.
@cache.cached(timeout=6 * 60 * 60, key_prefix="datasets")
@marshal_with(DatasetSchema(many=True))
def datasets():
    """
    Get datasets, populated with applicable urls for each dataset. Cached on 6hr intervals,
    based on time between new GLOSSIS files created
    """
    # TODO: move this out of here and into a task (with celery or something)

    # Loop over datasets
    for datasetinfo in DATASETS["info"]["datasets"]:
        id = datasetinfo["id"]

        # we have datasetinfo from the json file
        # also get more information by calling the /dataset url
        data = dataset(id, None)

        # update the dataset with relevant info from the Url
        datasetinfo.update(data)

    #  all of the above is inline, so we can return the original object.
    return jsonify(DATASETS["info"])


@app.route("/datasets/<string:datasetId>/<path:imageId>", methods=["GET"])
@use_kwargs(
    {
        "min": fields.Float(required=False),
        "max": fields.Float(required=False),
        "band": fields.Str(required=False),
    }
)
def dataset_url(*args, **kwargs):
    return dataset(*args, **kwargs)


@cache.memoize(timeout=6 * 60 * 60)
def dataset(datasetId, imageId, **kwargs):
    service_url_data = get_service_url(datasetId, "rasterService")
    access_url = service_url_data["url"]
    feature_url = service_url_data["featureinfo_url"]
    name = service_url_data["name"]
    protocol = service_url_data["protocol"]
    parameters = copy(service_url_data["parameters"])

    # Add any additional parameters given in request
    parameters.update(kwargs)

    if protocol == "fewsWms":
        data = get_fews_url(datasetId, name, access_url, feature_url, parameters)
    elif protocol == "hydroengine":
        data = get_hydroengine_url(
            datasetId, name, access_url, feature_url, parameters, image_id=imageId
        )

    else:
        logging.error(
            "{} protocol not recognized for dataset datasetId {}".format(
                protocol, datasetId
            )
        )
        data = {}

    dataset_dict = {}
    dataset_dict["rasterLayer"] = data

    # Populate flowmapLayer information
    service_url_data = get_service_url(datasetId, "flowmapService")
    if service_url_data:
        access_url = service_url_data["url"]
        name = service_url_data["name"]
        protocol = service_url_data["protocol"]
        parameters = service_url_data["parameters"]

        if protocol == "googlestorage":
            flowmap_data = get_google_storage_url(
                datasetId, name, access_url, parameters
            )
        else:
            logging.error(
                "{} protocol not recognized for flowmap datasetId {}".format(
                    protocol, datasetId
                )
            )
            flowmap_data = {}

        dataset_dict["flowmapLayer"] = flowmap_data

    return dataset_dict


@app.route("/stac/<string:gee_id>", methods=["GET"])
@cache.cached(timeout=6 * 60 * 60, key_prefix="stac")
def stac_gee(gee_id: str):
    """TODO Can be completely moved to HydroEngine."""

    # Retrieve static collection and remove old items
    coll = STAC_GEE.get(gee_id)
    if coll is None:
        abort(404, description=f"Collection {gee_id} not found")
    coll = deepcopy(coll)  # don't mutate template
    coll.remove_links(rel="item")
    coll.set_self_href(request.base_url)

    # Request new items from HydroEngine
    props = coll.properties
    data = request_gee(props["deltares:url"], props["deltares:name"])

    # Convert all timesteps into links
    if data is not None:

        timeseries = data.pop("imageTimeseries", [])
        # imageTimeseries doesn't contain current time
        timeseries.append({"imageId": data["imageId"], "date": data.get("date", "")})

        links = []
        for time in timeseries:
            imageid = time.pop("imageId")
            if imageid is None:
                imageid = "_"
            min = data.get("min", "")
            max = data.get("max", "")
            band = data.get("band", "") or ""
            link = Link(
                rel="item",
                target=f"{request.url_root}stac/{gee_id}/{imageid}?band={band}&min={min}&max={max}",
                media_type="application/geojson",
                properties=time,
                title=coll.id + "-" + imageid
                if imageid is not None
                else coll.id + "-single",
            )
            links.append(link)
        coll.add_links(links)

        coll.properties["deltares:band"] = data.get("band")
        coll.properties["deltares:min"] = data.get("min")
        coll.properties["deltares:max"] = data.get("max")
        coll.properties["deltares:palette"] = data.get("palette")

    return jsonify(coll.to_dict())


@cache.memoize(timeout=6 * 60 * 60)
def request_gee(url, dataset, imageid=None, **kwargs):
    """Request image info and WMS information from GEE."""
    # TODO This is a simpler replacement of `get_hydroengine_url`.
    print(url, dataset, imageid, kwargs)
    post_data = {
        "dataset": dataset,
        **kwargs,
    }
    if imageid is not None and imageid != "_":
        post_data["imageId"] = imageid
    resp = requests.post(url=url, json=post_data)

    if resp.status_code == 200:
        return resp.json()
    else:
        logging.error(resp.status_code, resp.text)
        return None


@app.route("/stac/<string:gee_id>/<path:image_id>", methods=["GET"])
def stac_item(gee_id: str, image_id: str):
    """TODO Can be completely moved to HydroEngine."""

    kwargs = {k: v for (k, v) in request.args.items() if v != ""}

    # Retrieve static template item
    coll = STAC_GEE.get(gee_id)
    if coll is None:
        abort(404, description=f"Collection {gee_id} not found")
    coll = deepcopy(coll)  # don't mutate template
    item = list(coll.get_items())[0]
    item = deepcopy(item)
    item.set_self_href(request.base_url)

    props = coll.properties
    data = request_gee(
        props["deltares:url"], props["deltares:name"], image_id, **kwargs
    )
    if data is not None:

        _ = data.pop("imageTimeseries", "")

        url = data.pop("url")
        if data["imageId"] is None:
            imageid = data["dataset"]
        else:
            imageid = data["imageId"].split("/")[-1]

        if "date" in data and data["date"] is not None:
            date = datetime.strptime(data["date"], "%Y-%m-%dT%H:%M:%S")
        else:
            date = datetime.now()

        item.id = coll.id + "-" + imageid
        item.assets["visual"].href = url
        item.properties.update(
            {"deltares:" + key: value for (key, value) in data.items()}
        )
        item.datetime = date

        return jsonify(item.to_dict())
    else:
        abort(500, description="Can't reach GEE.")


# TODO Load the stac collection and set root url dynamically,
# while mimicking the static browsing here.
@app.route("/static_stac/<path:filepath>")
def stac(filepath: str):
    """Serve static STAC collection."""
    return send_from_directory(stacdir.resolve(), filepath)


@app.route("/", methods=["GET"])
def root():
    """
    Redirect default page to API docs.
    """
    return redirect(url_for("flask-apispec.swagger-ui"))


docs.register(datasets)
docs.register(dataset_url)
docs.register(timeseries)
docs.register(locations)
docs.register(stac)
docs.register(stac_item)


def main():
    app.run(threaded=True)


if __name__ == "__main__":
    main()
