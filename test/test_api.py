#!/usr/bin/env python
# Copyright API authors
"""Test code."""

import json
import os
import pytest

from api import server


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
    r = api.requests.post(url=url, files=files, params={"dir_path": "/tmp/test"})
    assert r.status_code == 201

    # Download token for uploaded file
    params = {'path': '/tmp/test/test.txt'}
    r = api.requests.post(url=api.url_for(server.Downloads), data=params)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert 'token' in data.keys()

    # Get file with the token
    r = api.requests.get(url=api.url_for(server.Download, token=data['token']))
    assert r.status_code == 200
    with open(file_path, 'rb') as f:
        assert r.content == f.read()


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
