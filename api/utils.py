import os.path
import re


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
                                   'opt', 'proc', 'root', 'run', 'sbin', 'srv', 'sys', 'tmp',
                                   'usr', 'var']:
            return False

    # Check the existence of the file
    if check_existence:
        if not os.path.isfile(path):
            return False

    return True
