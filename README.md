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
- `UPLOADED_FILE_PATH_PREFIX`: Path to the directory to save uploaded files in.
- `PORT`: Port to run server on.
- `API_DEBUG`: Enable debug mode if true.
- `API_TOKEN`: Token as a string used for accessing external API while running tests. If not set, tests that use external API will be skipped.


## Tips

### How to set directory to store uploaded files

Set UPLOADED_FILE_PATH_PREFIX environmental variable. If not set, `/opt/uploaded_data` will be used.

### How to test with meta-store service

Set API_TOKEN environmental variable on running tests. The test will be skipped otherwise.
