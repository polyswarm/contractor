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

# Install solc that PolySwarm uses by defaul
RUN mkdir -p ~/.py-solc/solc-v0.5.3/bin \
    && wget -O ~/.py-solc/solc-v0.5.3/bin/solc https://github.com/ethereum/solidity/releases/download/v0.5.3/solc-static-linux \
    && chmod +rx ~/.py-solc/solc-v0.5.3/bin/solc

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN set -x && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN set -x && pip install .

CMD ["./docker/deploy.sh"]
