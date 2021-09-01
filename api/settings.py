import os

default_uploaded_file_path_prefix = os.path.join(
    os.sep,
    'opt',
    'uploaded_data',
)
UPLOADED_FILE_PATH_PREFIX = os.environ.get('UPLOADED_FILE_PATH_PREFIX',
                                           default_uploaded_file_path_prefix)

# Get service for api-meta-store
API_META_STORE_SERVICE_HOST = os.environ.get('API_META_STORE_SERVICE_HOST')
API_META_STORE_SERVICE_PORT = os.environ.get('API_META_STORE_SERVICE_PORT')
if API_META_STORE_SERVICE_HOST and API_META_STORE_SERVICE_PORT:
    META_STORE_SERVICE = f'{API_META_STORE_SERVICE_HOST}:{API_META_STORE_SERVICE_PORT}'
else:
    META_STORE_SERVICE = 'https://demo.dataware-tools.com/api/latest/meta_store'
