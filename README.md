# Contractor

Deploy contracts without truffle

Clone with `--recursive` or run `git submodule update --init --recursive` to fetch all submodules

## Compiling

Compile contracts with `contractor compile`, command returns non-zero on any compilation error or if no modifications to bytecode detected

## Deploying

Deploy contracts with `contractor deploy`, must provide a config file, private key file and password

## Consul

Ouput from compile and deploy steps can be pushed to consul with `contractor consul push`.
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

## Tests

Plan is to port truffle tests over to `ethereum.tester`, currently TODO
