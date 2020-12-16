#!/usr/bin/env python
# Copyright API authors
"""The API server."""

import json
import os

from dataware_tools_api_helper import get_jwt_payload_from_request
from dataware_tools_api_helper import get_catalogs
from dataware_tools_api_helper import get_forward_headers
import responder
import requests
from urllib.parse import quote

# Metadata
description = "An API for downloading files."
terms_of_service = "http://tools.hdwlab.com/terms/"
contact = {
    "name": "API Support",
    "url": "http://tools.hdwlab.com/support",
    "email": "contact@hdwlab.co.jp",
}
license = {
    "name": "Apache 2.0",
    "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
}

# Initialize app
api = responder.API(
    title="API for downloading files",
    version="1.0",
    openapi="3.0.2",
    docs_route='/docs',
    description=description,
    terms_of_service=terms_of_service,
    contact=contact,
    license=license,
    cors=True,
    cors_params={
        'allow_origins': ['*'],
        'allow_methods': ['*']
    },
    secret_key=os.environ.get('SECRET_KEY', os.urandom(12))
)
catalogs = get_catalogs()
debug = False


@api.route('/')
def index(req, resp):
    """Index page."""
    jwt_payload = get_jwt_payload_from_request(req)
    res = {
        'jwt_payload': jwt_payload
    }
    resp.media = res


@api.route('/echo/{content}/{resp_type}')
def echo(_, resp, *, content, resp_type):
    if resp_type == 'json':
        resp.media = {'content': content}
    else:
        resp.text = content


@api.route('/healthz')
def healthz(_, resp):
    resp.text = 'ok'


@api.route('/file')
async def get_file(req, resp):
    """Return the corresponding file.

    Args:
        req (any): Request
        resp (any): Response
        *

    Returns:
        (any): Raw file

    """
    database_id = req.params.get('database_id', None)
    record_id = req.params.get('record_id', None)
    path = req.params.get('path', None)
    content_type = req.params.get('content_type', None)

    if content_type is not None:
        resp.headers['Content-Type'] = content_type

    elif all([database_id is not None, record_id is not None]):
        # Try to get content-type of the file from meta-data
        try:
            record_service = 'http://' + catalogs['api']['recordStore']['service']
            if debug:
                record_service = 'https://dev.tools.hdwlab.com/api/latest/record_store'
            try:
                forward_header = get_forward_headers(req)
            except AttributeError:
                forward_header = req.headers
            forward_header = {k: v for k, v in forward_header.items() if k not in ['host']}
            forward_header.update({'accept-encoding': 'json'})
            request_url = '{}/{}/records/{}'.format(
                record_service, quote(database_id), quote(record_id)
            )
            response = requests.get(request_url, headers=forward_header)
            record_info = json.loads(response.text)
            corresponding_file = next(filter(lambda x: x['path'] == path, record_info['files']))
            resp.headers['Content-Type'] = corresponding_file['content-type']
        except Exception as e:
            print(str(e))

    if not os.path.isfile(path):
        resp.status_code = 404
        resp.media = {'reason': 'No such file'}
        return

    async def shout_stream(filepath, chunk_size=8192):
        with open(filepath, 'rb') as f:
            while True:
                buffer = f.read(chunk_size)
                if buffer:
                    yield buffer
                else:
                    break

    resp.stream(shout_stream, path)


if __name__ == '__main__':
    debug = os.environ.get('API_DEBUG', '') in ['true', 'True', 'TRUE', '1']
    print('Debug: {}'.format(debug))
    debug = debug
    api.run(debug=debug)
