#!/usr/bin/env python
# Copyright API authors
"""The API server."""

from datetime import datetime, timedelta
import hashlib
import json
import os
import time

import jwt
import responder
import requests
from urllib.parse import quote

from dataware_tools_api_helper import get_jwt_payload_from_request
from dataware_tools_api_helper import get_catalogs
from dataware_tools_api_helper import get_forward_headers

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
jwt_key = hashlib.sha256(
    api.secret_key.encode('utf-8') if isinstance(api.secret_key, str) else api.secret_key
).hexdigest()
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


@api.background.task
def regenerate_jwt_key():
    """Re-generate JWT key."""
    global jwt_key
    key = api.secret_key + datetime.now().strftime('%s')
    jwt_key = hashlib.sha256(
        key.encode('utf-8') if isinstance(key, str) else key
    ).hexdigest()
    print('JWT key has been regenerated')
    time.sleep(int(os.environ.get('JWT_LIFETIME', '3600')))

    regenerate_jwt_key()


@api.route('/download')
class Downloads:
    async def on_post(self, req, resp):
        """Generate token for downloading a file.

        Args:
            req (any): Request object.
            resp (any): Response object.

        Returns:
            (json): A dict containing a download token.

        """
        data = await req.media()
        database_id = data.get('database_id', None)
        record_id = data.get('record_id', None)
        path = data.get('path', None)
        content_type = data.get('content_type', None)

        payload = {
            'database_id': database_id,
            'record_id': record_id,
            'path': path,
            'content_type': content_type
        }

        if all([database_id is not None, record_id is not None]):
            payload['content_type'] = _get_content_type(req, database_id, record_id, path)

        if not os.path.isfile(path):
            resp.status_code = 404
            resp.media = {'reason': 'No such file'}
            return

        # Encode payload
        jwt_lifetime = float(os.environ.get('JWT_LIFETIME', '3600'))
        payload.update({
            'iss': 'api-file-provider',
            'iat': datetime.utcnow(),
            'nbf': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=jwt_lifetime)
        })
        token = jwt.encode(payload, jwt_key, algorithm='HS256')

        # Convert to str
        if isinstance(token, bytes):
            token = token.decode('utf-8')

        # Returns
        resp.media = {
            'token': token
        }


@api.route('/download/{token}')
class Download:
    async def on_get(self, req, resp, *, token):
        """Return the corresponding file

        Args:
            req (any): Request object.
            resp (any): Response object.
            *
            token (str): download token.

        Returns:
            (any): Binary data

        """
        # Decode payload
        try:
            if isinstance(token, str):
                token = token.encode('utf-8')
            payload = jwt.decode(token, jwt_key, algorithm='HS256')
        except jwt.ExpiredSignatureError:
            resp.status_code = 403
            resp.media = {'reason': 'JWT expired'}
            return
        except jwt.InvalidSignatureError:
            resp.status_code = 403
            resp.media = {'reason': 'Invalid signature'}
            return

        # Prepare headers
        if payload.get('content_type', None) is not None:
            resp.headers['Content-Type'] = payload.get('content_type')

        # Check file
        if not os.path.isfile(payload.get('path')):
            resp.status_code = 404
            resp.media = {'reason': 'No such file: {}'.format(payload.get('path'))}
            return

        # Stream the file
        resp.stream(_shout_stream, payload.get('path'))


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
        resp.headers['Content-Type'] = _get_content_type(req, database_id, record_id, path)

    if not os.path.isfile(path):
        resp.status_code = 404
        resp.media = {'reason': 'No such file'}
        return

    resp.stream(_shout_stream, path)


async def _shout_stream(filepath, chunk_size=8192):
    with open(filepath, 'rb') as f:
        while True:
            buffer = f.read(chunk_size)
            if buffer:
                yield buffer
            else:
                break


def _get_content_type(req, database_id, record_id, path):
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
        return corresponding_file['content-type']
    except Exception as e:
        print(str(e))
        return None


if __name__ == '__main__':
    debug = os.environ.get('API_DEBUG', '') in ['true', 'True', 'TRUE', '1']
    print('Debug: {}'.format(debug))
    debug = debug
    regenerate_jwt_key()
    api.run(debug=debug)
