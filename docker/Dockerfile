FROM python:3.6-slim-stretch
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"

ENV DOCKERIZE_VERSION v0.6.1

RUN apt-get update && apt-get install -y \
        build-essential \
        git \
        jq \
        libssl-dev \
        libudev-dev \
        libusb-1.0-0-dev \
        wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN set -x && pip install --no-cache-dir -r requirements.txt -r requirements_test.txt

COPY . .
RUN set -x && pip install .

# This will cause py-solc to get solc, which we can then package into the image.
RUN contractor install-solc

CMD ["./docker/deploy.sh"]
