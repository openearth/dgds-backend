import requests


def dd_shoreline(url, transect_id):
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
    # dd_transect = transform_dd(transect)
    dd_transect = transect

    return dd_transect
