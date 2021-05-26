# api-file-provider

An API for providing raw files so that users can download them

## How to build docker-image
```bash
$ ssh-agent
$ ssh-add
$ export DOCKER_BUILDKIT=1
$ docker built -t api-file-provider:latest . --ssh=default

```

## How to run the API server
Make sure to build the image first.
```bash
$ docker-compose up

```

## Tips

### How to test with meta-store service

Set API_TOKEN environmental variable on running tests. The test will be skipped otherwise.
