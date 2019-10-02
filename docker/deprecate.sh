#! /bin/bash

set -ex
mkdir -p consul
rm -f consul/*.json

# Pull any existing config for bytecode detection
if [ ! -z "$CONSUL_URI" ]; then
    echo "Pulling config from consul"
    dockerize -wait $CONSUL_URI -timeout 1000s
    contractor consul pull
fi

contractor deactivate community --network $SIDECHAIN --keyfile $SIDECHAIN_KEYFILE -a consul -i consul/sidechain.json
