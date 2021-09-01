# api-file-provider

An API for providing raw files so that users can download them

## How to build docker-image

```bash
$ ssh-agent
$ ssh-add
$ export DOCKER_BUILDKIT=1
$ docker build -t api-file-provider:latest . --ssh=default

```

## How to run the API server

Make sure to build the image first.

```bash
$ docker-compose up

```

## Environment variables

- `META_STORE_SERVICE`: URL of `api-meta-store`
- `UPLOADED_FILE_PATH_PREFIX`: Path to the directory to save uploaded files in. If not set, `/opt/uploaded_data` will be used.
- `API_IGNORE_PERMISSION_CHECK`: Whether to ignore checking permission via api-permission-manager, mainly for testing.
- `PORT`: Port to run server on.
- `API_DEBUG`: Enable debug mode if true.
- `API_TOKEN`: Token as a string used for accessing external API while running tests. If not set, tests that use external API will be skipped.
- `NUM_WORKERS`: Number of workers to run in parallel
