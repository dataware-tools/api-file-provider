#!/usr/bin/env python
# Copyright API authors
"""The API server."""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import quote

import aiofiles
import jwt
import requests
import responder
from dataware_tools_api_helper import get_forward_headers, get_jwt_payload_from_request

from api.settings import META_STORE_SERVICE, UPLOADED_FILE_PATH_PREFIX
from api.utils import get_valid_filename, is_file_in_directory, is_valid_path, get_jwt_key, get_check_permission_client

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
catalogs = {}
debug = os.environ.get('API_DEBUG', '') in ['true', 'True', 'TRUE', '1']


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
        file_uuid = data.get('file_uuid', None)
        record_id = data.get('record_id', None)
        content_type = data.get('content_type', None)

        # Validation
        if not file_uuid or not database_id:
            resp.status_code = 400
            resp.media = {
                'detail': 'Param file_uuid and database_id must be specified.',
            }
            return

        # Get file path (also for checking existance of the file)
        path = _get_file_path(req, database_id, file_uuid)
        if not path:
            resp.status_code = 404
            resp.media = {'detail': 'No such file'}
            return

        # Check permission
        permission_client = get_check_permission_client(req)
        try:
            permission_client.check_permissions('file:read', database_id)
        except PermissionError:
            resp.status_code = 403
            resp.media = {'detail': 'Operation not permitted.'}
            return

        payload = {
            'database_id': database_id,
            'record_id': record_id,
            'path': path,
            'content_type': content_type
        }

        if all([database_id is not None, record_id is not None]):
            payload['content_type'] = _get_content_type(req, database_id, record_id, path)

        if not is_valid_path(path, check_existence=True):
            resp.status_code = 404
            resp.media = {'detail': 'No such file'}
            return

        # Encode payload
        jwt_lifetime = float(os.environ.get('JWT_LIFETIME', '3600'))
        payload.update({
            'iss': 'api-file-provider',
            'iat': datetime.utcnow(),
            'nbf': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=jwt_lifetime)
        })
        key = get_jwt_key()
        token = jwt.encode(payload, key, algorithm='HS256')

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
            key = get_jwt_key()
            payload = jwt.decode(token, key, algorithm='HS256')
        except jwt.ExpiredSignatureError:
            resp.status_code = 403
            resp.media = {'detail': 'JWT expired'}
            return
        except jwt.InvalidSignatureError:
            resp.status_code = 403
            resp.media = {'detail': 'Invalid signature'}
            return

        # Check
        if payload.get('path', None) is None:
            raise ValueError('path not found')

        # Get file size
        path = payload.get('path')
        file_size = os.path.getsize(path)

        # Prepare headers
        resp.headers['Content-Transfer-Encoding'] = 'Binary'
        resp.headers['Content-Length'] = str(file_size)
        resp.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(
            os.path.basename(path)
        )
        if payload.get('content_type', None) is not None:
            resp.headers['Content-Type'] = payload.get('content_type')

        # Check file
        if not is_valid_path(path, check_existence=True):
            resp.status_code = 404
            resp.media = {'detail': 'No such file: {}'.format(path)}
            return

        # Get range request
        asked_range = req.headers.get('Range', None)
        try:
            bytes_to_start = int(asked_range.split('=')[1].split('-')[0])
            bytes_to_end = min(int(asked_range.split('=')[1].split('-')[1]), file_size - 1)
        except (AttributeError, ValueError):
            bytes_to_start = 0
            bytes_to_end = file_size - 1

        # Set headers for range request
        resp.headers['Accept-Ranges'] = 'bytes'
        if asked_range is not None:
            resp.headers['Content-Range'] = f'bytes {bytes_to_start}-{bytes_to_end}/{file_size}'
            resp.headers['Content-Length'] = str(bytes_to_end - bytes_to_start + 1)
            resp.status_code = 206

        # Stream the file
        resp.stream(_shout_stream, path)


@api.route('/upload')
class Upload:
    async def on_post(self, req, resp):

        @api.background.task
        def save_file(save_file_path, file):
            # Create directory if not exist
            dir_path = os.path.dirname(save_file_path)
            os.makedirs(dir_path, exist_ok=True)

            # Save file
            with open(save_file_path, 'wb') as f:
                f.write(file['content'])

        data = await req.media(format='files')
        file = data['file']
        if 'metadata' in data.keys():
            file_metadata = json.loads(data['metadata']['content'].decode())
        else:
            file_metadata = {}
        database_id = req.params.get('database_id', '')
        record_id = req.params.get('record_id', '')

        # Check permission
        permission_client = get_check_permission_client(req)
        try:
            permission_client.check_permissions('file:write:add', database_id)
        except PermissionError:
            resp.status_code = 403
            resp.media = {'detail': 'Operation not permitted.'}
            return

        save_file_path = os.path.join(
            UPLOADED_FILE_PATH_PREFIX,
            f'database_{get_valid_filename(database_id)}',
            f'record_{get_valid_filename(record_id)}',
            file['filename'],
        )
        if not is_valid_path(save_file_path, check_existence=False):
            resp.status_code = 403
            resp.media = {
                'detail': f'Invalid path: {save_file_path}',
            }
            return
        if os.path.exists(save_file_path):
            resp.status_code = 409
            resp.media = {
                'detail': f'The file with the same path ({save_file_path}) already exists.',
            }
            return
        else:
            save_file(save_file_path, file)

        # Add metadata to meta-store
        fetch_success, fetch_res = _update_metastore(req, database_id, record_id, save_file_path,
                                                     file_metadata)

        if fetch_success and fetch_res is not None:
            resp.status_code = fetch_res.status_code if fetch_res.status_code != 200 else 201
            fetch_res_body = fetch_res.json()
            resp.media = {
                'save_file_path': save_file_path,
                **fetch_res_body
            }
            return

        else:
            resp.status_code = 500
            resp.media = {
                'detail': 'Metadata updating process returned no response'
            }
            return


@api.route('/delete')
class DeleteFile:
    async def on_delete(self, req: responder.Request, resp: responder.Response):
        """Delete file with the requested path.

        Args:
            req (responder.Request): Request object.
            resp (responder.Response): Response object.
            *

        """
        database_id = req.params.get('database_id', '')
        file_uuid = req.params.get('file_uuid', '')

        # Validation
        if not file_uuid or not database_id:
            resp.status_code = 400
            resp.media = {
                'detail': 'Param file_uuid and database_id must be specified.',
            }
            return

        # Get file path (also for checking existance of the file)
        file_path = _get_file_path(req, database_id, file_uuid)
        if not file_path:
            resp.status_code = 404
            resp.media = {'detail': 'No such file'}
            return

        # Check if path is in the UPLOADED_FILE_PATH_PREFIX directory
        if not is_file_in_directory(file_path, UPLOADED_FILE_PATH_PREFIX):
            resp.status_code = 403
            resp.media = {
                'detail': f'Deleting ({file_path}) is forbbiden.',
            }
            return

        # Check permission
        permission_client = get_check_permission_client(req)
        try:
            permission_client.check_permissions('file:write:delete', database_id)
        except PermissionError:
            resp.status_code = 403
            resp.media = {'detail': 'Operation not permitted.'}
            return

        # Detele file
        try:
            os.remove(file_path)
        except (PermissionError, IsADirectoryError):
            resp.status_code = 403
            resp.media = {
                'detail': f'Deleting ({file_path}) is forbbiden.',
            }
            return
        except FileNotFoundError:
            resp.status_code = 404
            resp.media = {
                'detail': f'The file ({file_path}) does not exist.',
            }
            return

        resp.status_code = 200
        return


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

    # Check permission
    permission_client = get_check_permission_client(req)
    try:
        permission_client.check_permissions('file:read', database_id)
    except PermissionError:
        resp.status_code = 403
        resp.media = {'detail': 'Operation not permitted.'}
        return

    if content_type is not None:
        resp.headers['Content-Type'] = content_type

    elif all([database_id is not None, record_id is not None]):
        resp.headers['Content-Type'] = _get_content_type(req, database_id, record_id, path)

    if not is_valid_path(path, check_existence=True):
        resp.status_code = 404
        resp.media = {'detail': 'No such file'}
        return

    # Get file size
    file_size = os.path.getsize(path)
    resp.headers['Content-Length'] = str(file_size)

    # Get range request
    asked_range = req.headers.get('Range', None)
    try:
        bytes_to_start = int(asked_range.split('=')[1].split('-')[0])
        bytes_to_end = min(int(asked_range.split('=')[1].split('-')[1]), file_size - 1)
    except (AttributeError, ValueError):
        bytes_to_start = 0
        bytes_to_end = file_size - 1

    # Set headers for range request
    resp.headers['Accept-Ranges'] = 'bytes'
    if asked_range is not None:
        resp.headers['Content-Range'] = f'bytes {bytes_to_start}-{bytes_to_end}/{file_size}'
        resp.headers['Content-Length'] = str(bytes_to_end - bytes_to_start + 1)
        resp.status_code = 206

    resp.stream(_shout_stream, path)


async def _shout_stream(filepath, chunk_size=8192, start=0, size=None):
    async with aiofiles.open(filepath, 'rb') as f:
        bytes_read = 0
        await f.seek(start)
        while size is None or bytes_read < size:
            bytes_to_read = min(chunk_size, size - bytes_read) if size is not None else chunk_size
            buffer = await f.read(bytes_to_read)
            if buffer:
                bytes_read += min(bytes_to_read, len(buffer))
                yield buffer
            else:
                break


def _get_content_type(req, database_id, record_id, path):
    # Try to get content-type of the file from meta-data
    try:
        # TODO: Don't use catalogs
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


def _update_metastore(
    req: responder.Request,
    database_id: str,
    record_id: str,
    save_file_path: str,
    file_metadata: dict,
) -> Tuple[bool, Optional[requests.models.Response]]:
    """Update metadata in metastore.

    Args:
        req (responder.Request)
        database_id (str)
        record_id (str)
        save_file_path (str)
        file_metadata (dict)

    Returns:
        (Tuple[bool, dict]): True if the post request succeeds, False otherwise.

    """
    try:
        forward_header = get_forward_headers(req)
    except AttributeError:
        forward_header = req.headers
    try:
        headers = {
            'authorization': forward_header['authorization']
        }
    except KeyError:
        return (False, None)
    request_data = {
        'record_id': record_id,
        'database_id': database_id,
        'path': save_file_path,
        **file_metadata
    }
    try:
        res = requests.post(f'{META_STORE_SERVICE}/databases/{database_id}/files',
                            json=request_data, headers=headers)
    except Exception:
        return (False, None)

    return (True, res)


def _get_file_path(req: responder.Request, database_id: str, uuid: str) -> Optional[str]:
    """Get file path based on specified database_id and file uuid.

    Args:
        req (responder.Request)
        database_id (str)
        uuid (str)

    Returns:
        Optional[str]

    """
    try:
        forward_header = get_forward_headers(req)
    except AttributeError:
        forward_header = req.headers

    try:
        headers = {
            'authorization': forward_header['authorization']
        }
    except KeyError:
        return None

    try:
        res = requests.get(f'{META_STORE_SERVICE}/databases/{database_id}/files/{uuid}', headers=headers)
        res_data = json.loads(res.text)
        return res_data['path']
    except Exception:
        return None


if __name__ == '__main__':
    print('Debug: {}'.format(debug))
    api.run(debug=debug)
