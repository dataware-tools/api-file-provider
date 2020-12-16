FROM python:3.8-slim as develop

# Basic Setting
ENV LANG="en_US.UTF-8"

# Install fundamental packages
RUN apt update \
  && apt install -y --no-install-recommends git gcc linux-libc-dev libc6-dev openssh-client \
  && apt -y clean \
  && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN python3 -m pip install --upgrade pip \
  && python3 -m pip install setuptools \
  && python3 -m pip install poetry \
  && poetry config virtualenvs.create false \
  && rm -rf ~/.cache/pip

# Copy files and install dependencies
RUN mkdir -p /opt/app
COPY pyproject.toml poetry.loc[k] /opt/app/
WORKDIR /opt/app
RUN poetry install || poetry update

# Get catalogs
RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=ssh git clone git@github.com:dataware-tools/protocols.git /opt/protocols
ENV APP_CATALOG=/opt/protocols/catalogs/app.json
ENV API_CATALOG=/opt/protocols/catalogs/api.json

# Copy remaining files
COPY . /opt/app
ENV PYTHONPATH /opt/app:${PYTHONPATH}

# Default CMD
CMD ["python", "/opt/app/api/server.py"]
