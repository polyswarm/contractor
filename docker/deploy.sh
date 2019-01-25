#! /bin/bash

set -ex

rm -rf consul
mkdir consul

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

# Deploy to sidechain first, as it's cheaper (free) in the case of failure
echo "Deploying to sidechain"
contractor deploy --chain side --network $SIDECHAIN --keyfile $SIDECHAIN_KEYFILE -a consul -o consul/sidechain.json
echo "Deploying to homechain"
contractor deploy --chain home --network $HOMECHAIN --keyfile $HOMECHAIN_KEYFILE -a consul -o consul/homechain.json

# These configuration options are polyswarmd specific
jq -n \
    --argjson ipfs_uri "\"$IPFS_URI\"" \
    --argjson artifact_limit "$ARTIFACT_LIMIT" \
    --argjson auth_uri $([ -n "$AUTH_URI" ] && echo "\"$AUTH_URI\"" || echo null) \
    --argjson profiler_enabled $([ -n "$PROFILER_ENABLED" -a "x$PROFILER_ENABLED" != "x0" ] && echo true || echo false) \
    -f docker/config.jq > consul/config.json

# Push configuration to consul
if [ ! -z "$CONSUL_URI" ]; then
    echo "Pushing config to consul"
    contractor consul push
fi
