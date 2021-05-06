#!/usr/bin/env python
# Copyright API authors
"""Test code."""

import json
import os
import pytest
import time

from pydtk.db import V4DBHandler as DBHandler

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


def test_upload_201(api):
    file_path = 'test/files/text.txt'
    files = {'file': ('test.txt', open(file_path, 'rb'), "anything")}
    url = api.url_for(server.Upload)
    record_id = '016_00000000030000000240'
    database_id = 'Driving Behavior Database'
    file_metadata = {
        'file_metadata_string': 'string_data',
        'file_metadata_int': 10,
        'file_medadata_dict': {'key1': 'value1', 'key2': 'value2'},
        'file_medadata_list': [1, 2, 3],
    }
    params = {
        'record_id': record_id,
        'database_id': database_id,
        'file_metadata': json.dumps(file_metadata),
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

    # Check if metadata saved in pydtk
    handler = DBHandler(
        db_class='meta',
    )
    handler.read(pql=f'path == regex(".*/{os.path.basename(save_file_path)}")')
    match_data = next(handler)
    assert match_data['path'] == save_file_path
    assert match_data['record_id'] == record_id
    assert match_data['database_id'] == database_id
    assert match_data['file_metadata_string'] == 'string_data'
    assert match_data['file_metadata_int'] == 10
    assert match_data['file_medadata_dict'] == {'key1': 'value1', 'key2': 'value2'}
    assert match_data['file_medadata_list'] == [1, 2, 3]


def test_upload_database_404(api):
    file_path = 'test/files/text.txt'
    files = {'file': ('test.txt', open(file_path, 'rb'), "anything")}
    url = api.url_for(server.Upload)
    params = {'record_id': '016_00000000030000000240', 'database_id': 'database that does not exist'}
    r = api.requests.post(url=url, files=files, params=params)
    assert r.status_code == 404


def test_upload_record_404(api):
    file_path = 'test/files/text.txt'
    files = {'file': ('test.txt', open(file_path, 'rb'), "anything")}
    url = api.url_for(server.Upload)
    params = {'record_id': 'record that does not exist', 'database_id': 'Driving Behavior Database'}
    r = api.requests.post(url=url, files=files, params=params)
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
