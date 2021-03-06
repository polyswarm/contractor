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

# Will fail if contracts fail to compile or if bytecode is not modified, logs
# will indicate which scenario occurred
echo "Compiling contracts"
contractor compile -o consul

if [[ -f "consul/sidechain.json" ]]; then
    echo "Deactivating existing sidechain BountyRegistry"
    contractor deactivate contract --chain side --network $SIDECHAIN --keyfile $SIDECHAIN_KEYFILE -a consul -i consul/sidechain.json BountyRegistry
fi

# Deploy to sidechain first, as it's cheaper (free) in the case of failure
echo "Deploying to sidechain"
contractor deploy --chain side --network $SIDECHAIN --keyfile $SIDECHAIN_KEYFILE -a consul -o consul/sidechain.json
echo "Deploying to homechain"
contractor deploy --chain home --network $HOMECHAIN --keyfile $HOMECHAIN_KEYFILE -a consul -o consul/homechain.json

# Push configuration to consul
if [ ! -z "$CONSUL_URI" ]; then
    echo "Pushing config to consul"
    contractor consul push
fi
