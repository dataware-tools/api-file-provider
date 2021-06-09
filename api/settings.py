import os

default_uploaded_file_path_prefix = os.path.join(
    os.sep,
    'opt',
    'uploaded_data',
)
UPLOADED_FILE_PATH_PREFIX = os.environ.get('UPLOADED_FILE_PATH_PREFIX', default_uploaded_file_path_prefix)

METASTORE_DEV_SERVICE = 'https://dev.tools.hdwlab.com/api/latest/meta_store'
METASTORE_PROD_SERVICE = os.environ.get("METASTORE_PROD_SERVICE", 'https://dev.tools.hdwlab.com/api/latest/meta_store')
