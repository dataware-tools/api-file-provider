#!/usr/bin/env python
# Copyright API authors
"""Test code."""

import json
import os
import pytest
import time

from api import server
from api.settings import UPLOADED_FILE_PATH_PREFIX


@pytest.fixture
def api():
    return server.api


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


def test_upload_201_metadata_updated_properly(api):
    file_path = 'test/files/text.txt'
    file_metadata = {
        'file_metadata_string': 'string_data',
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
    record_id = 'test_record'
    database_id = 'test_database'
    params = {
        'record_id': record_id,
        'database_id': database_id,
    }
    r = api.requests.post(url=url, files=files, params=params)
    assert r.status_code == 201

    # TODO: Check file metadata updated in meta-store
    assert False


# TODO: Add 404 tests


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
