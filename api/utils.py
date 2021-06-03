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
