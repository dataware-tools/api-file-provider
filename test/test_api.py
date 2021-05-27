#!/usr/bin/env python
# Copyright API authors
"""Test code."""

import json
import os
import pytest
import requests
import shutil
import time
from urllib.parse import quote

from api import server
from api.settings import (
    UPLOADED_FILE_PATH_PREFIX,
    METASTORE_DEV_SERVICE,
)
API_TOKEN = os.environ.get('API_TOKEN', None)
skip_if_token_unset = pytest.mark.skipif(
    not API_TOKEN,
    reason="Requires API_TOKEN environment set",
)
AUTH_HEADERS = {'authorization': f'Bearer {API_TOKEN}'}


@pytest.fixture
def api():
    return server.api


@pytest.fixture
def setup_metastore_data():
    """Setup data for testing at metaStore."""
    database_id = 'database_for_testing_api_file_provider'
    record_id = 'record_for_testing_api_file_provider'
    # Add database
    requests.post(url=f'{METASTORE_DEV_SERVICE}/databases', headers=AUTH_HEADERS, json={'database_id': database_id})
    requests.post(url=f'{METASTORE_DEV_SERVICE}/records', headers=AUTH_HEADERS, json={'record_id': record_id})
    yield {'database_id': database_id, 'record_id': record_id}

    # Finalizer
    requests.delete(url=f'{METASTORE_DEV_SERVICE}/databases/{database_id}', headers=AUTH_HEADERS)
    requests.delete(url=f'{METASTORE_DEV_SERVICE}/records/{record_id}', headers=AUTH_HEADERS)


def delete_database_directory(database_id: str):
    """Delete directory that uploaded files are stored for specific database_id."""
    directory_for_database = os.path.join(
        UPLOADED_FILE_PATH_PREFIX,
        f'database_{database_id}',
    )
    if os.path.exists(directory_for_database):
        shutil.rmtree(directory_for_database)


def test_healthz(api):
    r = api.requests.get(url=api.url_for(server.healthz))
    assert r.text == 'ok'


def test_index(api):
    r = api.requests.get(url=api.url_for(server.index))
    data = json.loads(r.text)
    assert 'jwt_payload' in data.keys()


def assert_file_get_200(api, file_path, content_type=None):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.get(url=api.url_for(server.get_file), params=params)
    assert r.status_code == 200
    if content_type is not None:
        assert r.headers['Content-Type'] == content_type
    with open(file_path, 'rb') as f:
        assert r.content == f.read()


file_pathes = [
    ('/opt/app/test/files/text.txt', 'text/plain'),
    ('/opt/app/test/files/records/sample/data/records.bag', 'application/rosbag'),
]


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_file_get_200(api, file_path, content_type):
    assert_file_get_200(api, file_path, content_type)


def test_file_get_404(api):
    r = api.requests.get(url=api.url_for(server.get_file),
                         params={'path': 'a-file-that-does-not-exist'})
    assert r.status_code == 404


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_download_200(api, file_path, content_type):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.post(url=api.url_for(server.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    # Get file with the token
    r = api.requests.get(url=api.url_for(server.Download, token=data['token']))
    if content_type is not None:
        assert r.headers['Content-Type'] == content_type
    assert os.path.basename(file_path) in r.headers['Content-Disposition']
    with open(file_path, 'rb') as f:
        assert r.content == f.read()


def test_downloads_404(api):
    r = api.requests.post(url=api.url_for(server.Downloads),
                          data={'path': 'a-file-that-does-not-exist'})
    assert r.status_code == 404


def test_upload_201_file_uploaded_properly(api):
    file_path = 'test/files/text.txt'
    file_metadata = {}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    url = api.url_for(server.Upload)
    record_id = 'test_record'
    database_id = 'test_database'
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=url, files=files, params=params)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert 'save_file_path' in data.keys()
    save_file_path = data['save_file_path']

    time.sleep(0.5)

    # Download token for uploaded file
    params = {'path': save_file_path}
    r = api.requests.post(url=api.url_for(server.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    # Get file with the token
    r = api.requests.get(url=api.url_for(server.Download, token=data['token']))
    assert r.status_code == 200
    with open(file_path, 'rb') as f:
        assert r.content == f.read()

    # Detele uploaded files
    delete_database_directory(database_id)


def test_upload_409_duplicated_file(api):
    file_path = 'test/files/text.txt'
    file_metadata = {}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    url = api.url_for(server.Upload)
    record_id = 'test_record'
    database_id = 'test_database'
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=url, files=files, params=params)
    assert r.status_code == 201

    r = api.requests.post(url=url, files=files, params=params)
    assert r.status_code == 409

    # Detele uploaded files
    delete_database_directory(database_id)


@skip_if_token_unset
def test_upload_201_metadata_updated_properly(api, setup_metastore_data):
    file_path = 'test/files/text.txt'
    file_metadata = {
        'file_metadata_string': 'string_data',
        'file_metadata_string_japanese': '日本語テスト',
        'file_metadata_int': 10,
        'file_medadata_dict': {'key1': 'value1', 'key2': 'value2'},
        'file_medadata_list': [1, 2, 3],
    }
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        # Add json file for metadata contents
        # Reference:
        # - https://stackoverflow.com/a/35940980
        # - How to request in JS: https://stackoverflow.com/a/50774380
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    url = api.url_for(server.Upload)
    record_id = setup_metastore_data['record_id']
    database_id = setup_metastore_data['database_id']
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=url, files=files, params=params, headers=AUTH_HEADERS)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert 'save_file_path' in data.keys()
    save_file_path = data['save_file_path']

    # Detele uploaded files
    delete_database_directory(database_id)

    # Check file metadata updated in meta-store
    # TODO: Fix sub-string file_path based on base dir in pydtk
    url = f'{METASTORE_DEV_SERVICE}/files/{quote(save_file_path)[1:]}'
    r = requests.get(url=url, params=params, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'path' in data.keys()
    assert data['path'] == save_file_path
    assert 'contents' in data.keys()
    assert data['contents'] == file_metadata


# TODO: Add 404 tests


def test_delete_file_200(api):
    file_path = 'test/files/text.txt'
    file_metadata = {}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    record_id = 'test_record'
    database_id = 'test_database'
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=api.url_for(server.Upload), files=files, params=params)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert 'save_file_path' in data.keys()
    save_file_path = data['save_file_path']

    params = {
        'path': save_file_path,
    }
    r = api.requests.delete(url=api.url_for(server.DeleteFile), params=params)
    assert r.status_code == 200

    # Check whether the is file deleted
    params = {'path': save_file_path}
    r = api.requests.post(url=api.url_for(server.Downloads), data=params)
    assert r.status_code == 404


def test_delete_file_404(api):
    params = {
        'path': '/file_path_that_does_not_exist',
    }
    r = api.requests.delete(url=api.url_for(server.DeleteFile), params=params)
    assert r.status_code == 404


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_download_403(api, file_path, content_type):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.post(url=api.url_for(server.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    token = data['token'] + 'aaaaaaa'

    # Get file with the token
    r = api.requests.get(url=api.url_for(server.Download, token=token))
    assert r.status_code == 403
