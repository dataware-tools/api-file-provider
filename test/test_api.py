#!/usr/bin/env python
# Copyright API authors
"""Test code."""

import json
import os
import shutil
import time
from urllib.parse import quote

import pytest
import requests

from api import main
from api.settings import META_STORE_SERVICE, UPLOADED_FILE_PATH_PREFIX

API_TOKEN = os.environ.get('API_TOKEN', None)
skip_if_token_unset = pytest.mark.skipif(
    not API_TOKEN,
    reason="Requires API_TOKEN environment set",
)
AUTH_HEADERS = {'authorization': f'Bearer {API_TOKEN}'}


@pytest.fixture
def api():
    return main.api


@pytest.fixture
def setup_metastore_data():
    """Setup data for testing at metaStore."""
    database_id = 'database_for_testing_api_file_provider'
    record_id = 'record_for_testing_api_file_provider'
    # Add database
    requests.post(url=f'{META_STORE_SERVICE}/databases', headers=AUTH_HEADERS, json={'database_id': database_id})
    requests.post(
        url=f'{META_STORE_SERVICE}/databases/{database_id}/records', headers=AUTH_HEADERS,
        json={'record_id': record_id},
    )
    yield {'database_id': database_id, 'record_id': record_id}

    # Finalizer
    requests.delete(url=f'{META_STORE_SERVICE}/databases/{database_id}', headers=AUTH_HEADERS)
    requests.delete(url=f'{META_STORE_SERVICE}/records/{record_id}', headers=AUTH_HEADERS)


def delete_database_directory(database_id: str):
    """Delete directory that uploaded files are stored for specific database_id."""
    directory_for_database = os.path.join(
        UPLOADED_FILE_PATH_PREFIX,
        f'database_{database_id}',
    )
    if os.path.exists(directory_for_database):
        shutil.rmtree(directory_for_database)


def test_healthz(api):
    r = api.requests.get(url=api.url_for(main.healthz))
    assert r.text == 'ok'


def test_index(api):
    r = api.requests.get(url=api.url_for(main.index))
    data = json.loads(r.text)
    assert 'jwt_payload' in data.keys()


def assert_file_get_200(api, file_path, content_type=None):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.get(url=api.url_for(main.get_file), params=params)
    assert r.status_code == 200
    if content_type is not None:
        assert r.headers['Content-Type'] == content_type
    with open(file_path, 'rb') as f:
        assert r.content == f.read()


file_pathes = [
    ('/opt/app/test/files/text.txt', 'text/plain'),
    ('/opt/app/test/files/records/sample/data/records.bag', 'application/rosbag'),
]

file_pathes_invalid = [
    ('/proc/self/environ', 'text/plain'),
    ('/etc/passwd', 'text/plain'),
]


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_file_get_200(api, file_path, content_type):
    assert_file_get_200(api, file_path, content_type)


def test_file_get_404(api):
    r = api.requests.get(url=api.url_for(main.get_file),
                         params={'path': 'a-file-that-does-not-exist'})
    assert r.status_code == 404


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_download_200(api, file_path, content_type):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.post(url=api.url_for(main.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    # Get file with the token
    r = api.requests.get(url=api.url_for(main.Download, token=data['token']))
    if content_type is not None:
        assert r.headers['Content-Type'] == content_type
    assert os.path.basename(file_path) in r.headers['Content-Disposition']
    with open(file_path, 'rb') as f:
        assert r.content == f.read()


def test_downloads_404(api):
    r = api.requests.post(url=api.url_for(main.Downloads),
                          data={'path': 'a-file-that-does-not-exist'})
    assert r.status_code == 404


@skip_if_token_unset
def test_upload_201_file_uploaded_properly(api, setup_metastore_data):
    file_path = 'test/files/text.txt'
    file_metadata = {"description": "test in api-file-provider"}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'metadata': (None, json.dumps(file_metadata), 'application/json'),
    }
    url = api.url_for(main.Upload)
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

    time.sleep(0.5)

    # TODO: pass below test
    # Download token for uploaded file
    params = {'path': save_file_path}
    r = api.requests.post(url=api.url_for(main.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    # Get file with the token
    r = api.requests.get(url=api.url_for(main.Download, token=data['token']))
    assert r.status_code == 200
    with open(file_path, 'rb') as f:
        assert r.content == f.read()

    # Detele uploaded files
    delete_database_directory(database_id)


@skip_if_token_unset
def test_upload_409_duplicated_file(api, setup_metastore_data):
    file_path = 'test/files/text.txt'
    file_metadata = {}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    url = api.url_for(main.Upload)
    record_id = setup_metastore_data['record_id']
    database_id = setup_metastore_data['database_id']
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=url, files=files, params=params, headers=AUTH_HEADERS)
    assert r.status_code == 201

    time.sleep(0.5)

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
    url = api.url_for(main.Upload)
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
    assert 'uuid' in data.keys()
    save_file_path = data['save_file_path']
    file_uuid = data['uuid']

    # Detele uploaded files
    delete_database_directory(database_id)

    # Check file metadata updated in meta-store
    url = f'{META_STORE_SERVICE}/databases/{database_id}/files/{file_uuid}'
    r = requests.get(url=url, params=params, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'path' in data.keys()
    assert data['path'] == save_file_path


# TODO: Add 404 tests


@skip_if_token_unset
def test_delete_file_200(api, setup_metastore_data):
    # Upload file for delete later
    file_path = 'test/files/text.txt'
    file_metadata = {}
    files = {
        'file': ('test.txt', open(file_path, 'rb'), 'anything'),
        'contents': (None, json.dumps(file_metadata), 'application/json'),
    }
    record_id = setup_metastore_data['record_id']
    database_id = setup_metastore_data['database_id']
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=api.url_for(main.Upload), files=files, params=params, headers=AUTH_HEADERS)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert 'save_file_path' in data.keys()
    save_file_path = data['save_file_path']

    time.sleep(0.5)

    # Delete file
    params = {
        'path': save_file_path,
    }
    r = api.requests.delete(url=api.url_for(main.DeleteFile), params=params)
    assert r.status_code == 200

    # Check whether the is file deleted
    params = {'path': save_file_path}
    r = api.requests.post(url=api.url_for(main.Downloads), data=params)
    assert r.status_code == 404

    # Detele uploaded files
    delete_database_directory(database_id)


def test_delete_file_404(api):
    params = {
        'path': os.path.join(
            UPLOADED_FILE_PATH_PREFIX,
            'file_path_that_does_not_exist',
        ),
    }
    r = api.requests.delete(url=api.url_for(main.DeleteFile), params=params)
    assert r.status_code == 404


def test_delete_file_delete_directory_get_403(api):
    path_to_directory = os.path.join(
        UPLOADED_FILE_PATH_PREFIX,
        'dir_to_delete_test',
    )
    os.makedirs(path_to_directory, exist_ok=True)
    params = {
        'path': path_to_directory,
    }
    r = api.requests.delete(url=api.url_for(main.DeleteFile), params=params)
    os.rmdir(path_to_directory)
    assert r.status_code == 403


def test_delete_file_outside_upload_directory_403(api):
    # Touch file
    path_to_file = '/tmp/file_to_delete'
    with open(path_to_file, 'w') as _:
        pass

    params = {
        'path': path_to_file,
    }
    r = api.requests.delete(url=api.url_for(main.DeleteFile), params=params)
    assert r.status_code == 403

    # Delete file
    os.remove(path_to_file)


@pytest.mark.parametrize("file_path, content_type", file_pathes)
def test_download_403(api, file_path, content_type):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.post(url=api.url_for(main.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    token = data['token'] + 'aaaaaaa'

    # Get file with the token
    r = api.requests.get(url=api.url_for(main.Download, token=token))
    assert r.status_code == 403


@pytest.mark.parametrize("file_path, content_type", file_pathes_invalid)
def test_invalid_path(api, file_path, content_type):
    params = {'path': file_path}
    if content_type is not None:
        params.update({'content_type': content_type})
    r = api.requests.post(url=api.url_for(main.Downloads), data=params)
    assert r.status_code == 404
