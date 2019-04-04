# Contractor

[![pipeline status](https://gitlab.polyswarm.io/externalci/contractor/badges/master/pipeline.svg)](https://gitlab.polyswarm.io/externalci/contractor/commits/master)
[![coverage report](https://gitlab.polyswarm.io/externalci/contractor/badges/master/coverage.svg)](https://gitlab.polyswarm.io/externalci/contractor/commits/master)

Deploy contracts without truffle

Clone with `--recursive` or run `git submodule update --init --recursive` to fetch all submodules

## Docker

Build docker image with `docker build -t polyswarm/contractor -f docker/Dockerfile .` from repository root

Docker image contains a `deploy.sh` script which will orchestrate a deployment across a homechain and a sidechain, and push results to consul.

If configuration already exists in Consul and no bytecode changes, deploy will be a no-op.
If bytecode changes are detected, all deployment steps will be re-run with the newly compiled contracts.

To force a redeploy, remove the `chain/<COMMUNITY>` key in consul and re-run.

## Compiling

Compile contracts with `contractor compile`, command returns non-zero on any compilation error or if no modifications to bytecode detected

## Deploying

Deploy contracts with `contractor deploy`, must provide a config file, private key file and password

## Consul

Output from compile and deploy steps can be pushed to consul with `contractor consul push`.
Can also pull configs to take advantange of bytecode detection

## Persistent deployment records

Pass `--db-uri` or set the environment variable `DB_URI`, deployments will be recorded along with contract ABI, bytecode, and other relevant data.

## Config format

Check out example config in `examples/example_config.yml`

## Adding deployment steps

1. Add a new python file in `src/contractor/steps`
1. Create a subclass of `contractor.steps.Step`
1. Declare any dependencies in the `DEPENDENCIES` set
1. New step will be automatically picked up and ordered

## Analysis

Currently supported analyses:

- [Solium/Ethlint](https://github.com/duaraghav8/Ethlint) - Requires `solium` in path
- [Slither](https://github.com/trailofbits/slither) - Requires `slither` in path

## Tests

Tests have been ported from old truffle test suite into unit tests in the `tests` directory, using `ethereum.tester`.

Coverage reporting is a TODO.
