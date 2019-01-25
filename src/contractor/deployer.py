import json
import logging
import os
import re

from contractor.db import Deployment, Contract
from contractor.git import get_git_status
from hexbytes import HexBytes

logger = logging.getLogger(__name__)

GAS_MULTIPLIER = 1.2


# For polyswarmd compatibility
# https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
def camel_case_to_snake_case(s):
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# https://stackoverflow.com/questions/19053707/converting-snake-case-to-lower-camel-case-lowercamelcase
# Unfortunate special case for ERC20Relay
def snake_case_to_camel_case(s):
    acronyms = {'ERC'}
    ret = ''.join(c.title() for c in s.split('_'))
    for a in acronyms:
        ret = ret.replace(a.lower().title(), a)
    return ret


class Deployer(object):
    def __init__(self, community, network, artifactsdir, record_git_status=False, session=None):
        self.__community = community
        self.__network = network
        self.__session = session

        self.contracts = {}
        self.deployment = None

        self.__scan_artifacts(artifactsdir)
        self.__record_deployment(record_git_status, artifactsdir)

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

    def __record_deployment(self, record_git_status, artifactsdir):
        if self.__session is not None:
            commit_hash = tree_dirty = None
            if record_git_status:
                commit_hash, tree_dirty = get_git_status(artifactsdir)
                logger.info('Recording deployment in database, commit_hash: %s, tree_dirty: %s', commit_hash,
                            tree_dirty)

                if tree_dirty:
                    logger.warning('Deploying with a dirty tree, may make tracking contract source difficult')
            else:
                logger.info('Recording deployment in database')

            self.deployment = Deployment(self.__community, self.__network.name, self.__network.network_id,
                                         self.__network.chain, commit_hash=commit_hash, tree_dirty=tree_dirty)
            self.__session.add(self.deployment)
            self.__session.commit()

    def __record_contract(self, name, deployed):
        if self.__session is not None and self.deployment is not None:
            contract_obj = self.contracts[name]
            logger.info('Recording contract %s:%s in database', name, contract_obj.address)

            contract = Contract(self.deployment, name, deployed, contract_obj.address, contract_obj.abi,
                                contract_obj.bytecode, self.__network.contract_config.get(name, {}))
            self.__session.add(contract)
            self.__session.commit()

    def __mark_deployment_success(self):
        if self.__session is not None and self.deployment is not None:
            # Mark any nondeployed contracts as built but not deployed
            nondeployed = {name for name in self.artifacts if name not in self.contracts}
            for name in nondeployed:
                logger.info('Recording non-deployed contract %s in database', name)

                abi = self.artifacts[name]['abi']
                bytecode = HexBytes(self.artifacts[name]['evm']['bytecode']['object'])
                contract = Contract(self.deployment, name, False, None, abi, bytecode,
                                    self.__network.contract_config.get(name, {}))
                self.__session.add(contract)

            self.deployment.succeeded = True
            self.__session.commit()

    def at(self, name, address, deployed=False):
        artifact = self.artifacts.get(name)
        if artifact is None:
            raise ValueError('No artifact {} in artifacts, have you compiled?'.format(name))

        contract = self.__network.w3.eth.contract(address=address, abi=artifact['abi'],
                                                  bytecode=artifact['evm']['bytecode']['object'])
        self.contracts[name] = contract
        self.__record_contract(name, deployed)

        return contract

    def deploy(self, name, *args, **kwargs):
        # TODO: Handle linking contracts, py-solc supports this but we don't use libs in our contracts
        if name in self.contracts:
            logger.warning('%s has already been deployed, re-deploying as requested', name)

        txopts = kwargs.pop('txopts', {})

        artifact = self.artifacts.get(name)
        if artifact is None:
            raise ValueError('Artifact {} not found, have you compiled?'.format(name))

        contract = self.__network.w3.eth.contract(abi=artifact['abi'],
                                                  bytecode=artifact['evm']['bytecode']['object'])
        call = contract.constructor(*args, **kwargs)

        logger.info('Deploying %s', name)

        txhash = self.transact(call, txopts)
        receipt = self.__network.wait_and_check_transaction(txhash)

        address = receipt.contractAddress
        logger.info('Deployed %s to %s', name, address)

        return self.at(name, address, deployed=True)

    def transact(self, call, txopts={}):
        opts = dict(self.__network.txopts())
        opts.update(txopts)

        # Use our estimate but don't exceed gas limit defined in config
        try:
            gas = int(call.estimateGas({'from': self.__network.account, **opts}) * GAS_MULTIPLIER)
            opts['gas'] = min(opts['gas'], gas)
        except ValueError as e:
            logger.warning('Error estimating gas, bravely trying anyway: %s', e)

        tx = call.buildTransaction(opts)

        signed_tx = self.__network.sign_transaction(tx)
        return self.__network.send_transaction(signed_tx)

    def dump_results(self, f):
        self.__mark_deployment_success()

        results = {camel_case_to_snake_case(name) + '_address': contract.address
                   for name, contract in self.contracts.items()}

        results['eth_uri'] = self.__network.eth_uri
        # XXX: Difference between these is subtle but irrelevant for our purposes
        results['chain_id'] = self.__network.network_id
        results['free'] = self.__network.gas_price == 0

        logger.info('Dumping deployment results to json')
        logger.debug('Deployment results: %s', json.dumps(results))
        json.dump(results, f)

    def load_results(self, f):
        logger.info('Loading deployment results from json')

        deployment_results = json.load(f)
        for key, address in deployment_results.items():
            self.at(snake_case_to_camel_case(key), address)
