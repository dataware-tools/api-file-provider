from distutils.dir_util import copy_tree
import os

import pytest


@pytest.fixture(autouse=True)
def setup_database(request):
    """Setup database for each test.
    # TODO: In-memory database would be a much better option.
    """
    PATH_TO_TMP_DATABASE = '/tmp/db_for_testing'
    # Set db host
    os.environ['PYDTK_META_DB_HOST'] = PATH_TO_TMP_DATABASE
    # Copy example db to /tmp
    copy_tree('./test/example_db', PATH_TO_TMP_DATABASE)
