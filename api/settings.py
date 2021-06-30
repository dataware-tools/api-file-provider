import os

default_uploaded_file_path_prefix = os.path.join(
    os.sep,
    'opt',
    'uploaded_data',
)
UPLOADED_FILE_PATH_PREFIX = os.environ.get('UPLOADED_FILE_PATH_PREFIX',
                                           default_uploaded_file_path_prefix)

META_STORE_SERVICE = os.environ.get('META_STORE_SERVICE',
                                    'https://demo.dataware-tools.com/api/latest/meta_store')
