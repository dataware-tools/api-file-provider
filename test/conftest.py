import os

import pytest


@pytest.fixture(scope='function', autouse=True)
def set_env_vars_for_testing():
    os.environ['API_IGNORE_PERMISSION_CHECK'] = 'true'
