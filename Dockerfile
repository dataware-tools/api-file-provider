FROM python:3.8-slim as develop

# Basic Setting
ENV LANG="en_US.UTF-8"

# Install fundamental packages
RUN apt update \
  && apt install -y --no-install-recommends git gcc linux-libc-dev libc6-dev \
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

# Copy remaining files
COPY . /opt/app
ENV PYTHONPATH /opt/app:${PYTHONPATH}

# Default CMD
CMD ["python", "/opt/app/api/server.py"]
