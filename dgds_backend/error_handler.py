"""Application error handlers."""
import traceback
import json

from flask import Blueprint, jsonify, abort
from webargs.flaskparser import parser
from werkzeug.exceptions import HTTPException

error_handler = Blueprint('errors', __name__)


# This error handler is necessary for usage with webargs validation
@parser.error_handler
def handle_request_parsing_error(err, req, schema, error_status_code, error_headers):
    abort(422, err.messages)


@error_handler.app_errorhandler(Exception)
def handle_unexpected_error(error):
    stack = traceback.format_exc()

    status_code = 500
    success = False
    response = {
        'success': success,
        'error': {
            'type': 'UnexpectedException',
            'message': str(error),
            'stack': stack
        }
    }

    return jsonify(response), status_code


@error_handler.app_errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response
