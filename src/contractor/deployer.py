import json
import logging
import os

logger = logging.getLogger(__name__)


class Deployer(object):
    def __init__(self, network, artifactsdir):
        self.__network = network
        self.__scan_artifacts(artifactsdir)

        self.contracts = {}

    def __scan_artifacts(self, artifact_dir):
        self.artifacts = {}
        for filename in os.listdir(artifact_dir):
            with open(os.path.join(artifact_dir, filename), 'r') as f:
                j = json.load(f)

            name = j.get('contractName')
            if name is None:
                logger.warning('%s is not a valid contract, skipping', filename)
                continue

            self.artifacts[name] = j

    def at(self, name, address):
        artifact = self.artifacts.get(name)
        if artifact is None:
            raise ValueError('No artifact {} in artifacts, have you compiled?'.format(name))

        contract = self.__network.w3.eth.contract(address=address, abi=artifact['abi'])
        self.contracts[name] = contract

        return contract

    def deploy(self, name, *args, **kwargs):
        # TODO: Handle linking contracts, py-solc supports this but we don't use libs in our contracts
        if name in self.contracts:
            logger.warning('%s has already been deployed, re-deploying as requested', name)

        txopts = kwargs.pop('txopts', {})

        artifact = self.artifacts.get(name)
        if artifact is None:
            raise ValueError('Artifact {} not found, have you compiled?'.format(name))

        contract = self.__network.w3.eth.contract(abi=artifact['abi'], bytecode=artifact['evm']['bytecode']['object'])
        call = contract.constructor(*args, **kwargs)

        logger.info('Deploying %s', name)

        txhash = self.transact(call, txopts)
        receipt = self.__network.wait_for_transaction(txhash)

        address = receipt.contractAddress

        # TODO: Record deployment in persistent db
        logger.info('Deployed %s to %s', name, address)

        return self.at(name, address)


    def transact(self, call, txopts={}):
        opts = dict(self.__network.txopts)
        opts.update(txopts)

        tx = call.buildTransaction(opts)
        signed_tx = self.__network.sign_transaction(tx)
        return self.__network.send_transaction(signed_tx)

    def dump_results(self, f):
        logger.info('Dumping deployment results to json')
        json.dump({name: contract.address for name, contract in self.contracts.items()}, f)

    def load_results(self, f):
        logger.info('Loading deployment results to json')

        deployment_results = json.load(f)
        for name, address in deployment_results.items():
            self.at(name, address)

