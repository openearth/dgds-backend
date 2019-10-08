from marshmallow import Schema, fields

class DatasetSchema(Schema):
    id = fields.Str()
    name = fields.Str()
    locationIdField = fields.Str()
    rasterActiveOnLoad = fields.Bool()
    pointData = fields.Str()
    units = fields.Str()
    timeSpan = fields.Str()
    themes = fields.List(fields.Str())
    vectorLayer = fields.Dict()
    rasterLayer = fields.Dict()

class TimeSerieSchema(Schema):
    """See DigitalDelta API 2.0."""
    paging = fields.Dict()
    provider = fields.Dict()
    results = fields.List(fields.Dict())
