from distutils.util import strtobool
import os.path
import re

from dataware_tools_api_helper import get_forward_headers
from dataware_tools_api_helper.permissions import CheckPermissionClient, DummyCheckPermissionClient
import responder


def get_valid_filename(name):
    """
    Taken from https://github.com/django/django/blob/0b79eb36915d178aef5c6a7bbce71b1e76d376d3/django/utils/text.py#L225
    and edited.
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> get_valid_filename("john's portrait in 2004.jpg")
    'johns_portrait_in_2004.jpg'
    """
    s = str(name).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    return s


def is_file_in_directory(file: str, directory: str) -> bool:
    """Return if the file is in the directory.
    Taken from https://stackoverflow.com/q/3812849.

    Args:
        file (str): Path to file to check.
        directory (str): path to directory to check.

    Returns:
        (bool): Whether the file is in the specified directory.

    """
    # make both absolute
    directory = os.path.join(os.path.realpath(directory), '')
    file = os.path.realpath(file)

    # return true, if the common prefix of both is equal to directory
    # e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b
    return os.path.commonprefix([file, directory]) == directory


def is_valid_path(path: str, check_existence=False) -> bool:
    """Checks if the path is valid.

    Args:
        path (str): File path
        check_existence (bool): If True, this function also checks the existence of the file

    Returns:
        (bool): True if the path is valid, otherwise False

    """
    # Avoid Directory Traversal
    abspath = os.path.abspath(os.path.realpath(path))
    abspath_splitted = abspath.split(os.sep)
    if len(abspath_splitted) < 2:
        return False
    else:
        if abspath_splitted[1] in ['bin', 'boot', 'dev', 'etc', 'home', 'lib', 'lib64', 'media',
                                   'proc', 'root', 'run', 'sbin', 'srv', 'sys', 'tmp', 'usr',
                                   'var']:
            return False

    # Check the existence of the file
    if check_existence:
        if not os.path.isfile(path):
            return False

    return True


def get_jwt_key() -> str:
    """Get JWT Key."""
    try:
        with open('/tmp/api-file-provider-jwt-key', 'r') as f:
            key = f.read()
        return key
    except IOError:
        return ''


def save_jwt_key(key: str):
    """Get JWT Key."""
    with open('/tmp/api-file-provider-jwt-key', 'w') as f:
        f.write(key)


def get_check_permission_client(req: responder.Request):
    """Get a client for checking permission.

    Args:
        req (responder.Request): Authorization request header.
    """
    if strtobool(os.environ.get('API_IGNORE_PERMISSION_CHECK', 'false')):
        return DummyCheckPermissionClient('')

    try:
        forward_header = get_forward_headers(req)
    except AttributeError:
        forward_header = req.headers
    auth_header = forward_header.get('authorization', '')
    return CheckPermissionClient(auth_header)


def get_database_id_from_file_path(file_path: str):
    """Get a database_id from file_path.

    Args:
        file_path (str)
    """
    directory_for_database = file_path.split(os.path.sep)[-3]
    return directory_for_database[9:]
