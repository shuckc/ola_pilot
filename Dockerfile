FROM ubuntu:20.04

ENV TZ=Europe DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    tzdata \
    build-essential \
    checkinstall \
    libreadline-gplv2-dev \
    libncursesw5-dev \
    libssl-dev \
    libsqlite3-dev \
    tk-dev \
    libgdbm-dev \
    libc6-dev \
    libbz2-dev \
    software-properties-common \
    curl \
# Install python 3.11
    && apt-get update \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get install -y --no-install-recommends \
    python3.11

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
RUN mkdir -p /app/
COPY requirements.txt /app
RUN pip install -r /app/requirements.txt
RUN pip install mypy pandas-stubs

COPY ola/ /app/ola/
COPY stubs/ /app/stubs/
COPY *.py /app/
WORKDIR /app/
RUN ls -la /app
RUN pytest
RUN black --check *.py
RUN mypy --check-untyped-defs *.py
