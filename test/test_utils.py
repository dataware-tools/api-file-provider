#!/usr/bin/env python
# Copyright API authors
"""Test utils module."""


def test_get_database_id_from_file_path():
    from api.utils import get_database_id_from_file_path
    assert get_database_id_from_file_path(
        (
            '/opt/test_upload_file'
            '/database_database_for_testing_api_file_provider'
            '/record_record_for_testing_api_file_provider'
            '/test.txt'
        )
    ) == 'database_for_testing_api_file_provider'
