import yaml

from enum import Enum
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware


class Chain(Enum):
    HOMECHAIN = 1
    SIDECHAIN = 2

    @staticmethod
    def from_str(s):
        if s.lower() == 'home':
            return Chain.HOMECHAIN
        elif s.lower() == 'side':
            return Chain.SIDECHAIN
        else:
            raise ValueError('Chain must be either home or side')


class NetworkConfig(object):
    def __init__(self, name, eth_uri, network_id, gas_limit, gas_price, timeout, contract_config, chain):
        self.name = name
        self.eth_uri = eth_uri
        self.network_id = network_id
        self.gas_limit = gas_limit
        self.gas_price = gas_price
        self.timeout = timeout
        self.contract_config = contract_config
        self.chain = chain

        self.w3 = None
        self.priv_key = None
        self.account = None

        self.validate()

    def connect(self, keyfile, password):
        self.w3 = Web3(HTTPProvider(self.eth_uri))
        self.w3.middleware_stack.inject(geth_poa_middleware, layer=0)
        self.priv_key = self.w3.eth.account.decrypt(keyfile.read(), password)
        self.account = self.w3.eth.account.privateKeyToAccount(self.priv_key).address

    @classmethod
    def from_dict(cls, d, name, default_contract_config, chain):
        eth_uri = d.get('eth_uri')
        network_id = d.get('network_id')
        gas_limit = d.get('gas_limit')
        gas_price = d.get('gas_price')
        timeout = d.get('timeout', 240)

        # Copy default contract config and apply any overrides if applicable
        contract_config = dict(default_contract_config)
        contract_config.update(d.get('contracts', {}))

        return cls(name, eth_uri, network_id, gas_limit, gas_price, timeout, contract_config, chain)

    def validate(self):
        pass

    @property
    def txopts(self):
        return {
            # XXX: Difference between these is subtle but irrelevant for our purposes
            'chainId': self.network_id,
            'gas': self.gas_limit,
            'gasPrice': self.gas_price,
            # TODO: If async, need to track nonce same way as in polyswarm-client
            'nonce': self.w3.eth.getTransactionCount(self.account),
        }

    def sign_transaction(self, tx):
        return self.w3.eth.account.signTransaction(tx, self.priv_key)

    def send_transaction(self, signed_tx):
        return self.w3.eth.sendRawTransaction(signed_tx.rawTransaction)

    # Helper methods for waiting for a tx to be mined and checking its status
    def wait_for_transaction(self, txhash):
        return self.w3.eth.waitForTransactionReceipt(txhash, timeout=self.timeout)

    def wait_for_transactions(self, txhashes):
        # TODO: asyncio-ify operations and use asyncio.gather or similar, using blocking API for now
        ret = []
        for txhash in txhashes:
            ret.append(self.wait_for_transaction(txhash))
        return ret

    def check_transaction(self, txhash):
        tx = self.w3.eth.getTransaction(txhash)
        receipt = self.w3.eth.getTransactionReceipt(txhash)

        return receipt is not None and receipt['gasUsed'] < tx['gas'] and receipt['status'] == 1

    def check_transactions(self, txhashes):
        return all([self.check_transaction(txhash) for txhash in txhashes])

    def wait_and_check_transaction(self, txhash):
        receipt = self.wait_for_transaction(txhash)
        if not self.check_transaction(txhash):
            raise Exception('Transaction {0} failed, check network state', txhash)
        return receipt

    def wait_and_check_transactions(self, txhashes):
        receipts = self.wait_for_transactions(txhashes)
        if not self.check_transactions(txhashes):
            raise Exception('Transaction failed, check network state')
        return receipts


class Config(object):
    def __init__(self, networks, default_contract_config):
        self.networks = networks
        self.default_contract_config = default_contract_config

        self.validate()

    @classmethod
    def from_dict(cls, d, chain):
        default_contract_config = d.get('contracts', {})
        networks = {k: NetworkConfig.from_dict(v, k, default_contract_config, chain) for k, v in
                    d.get('networks', {}).items()}

        return cls(networks, default_contract_config)

    @classmethod
    def from_yaml(cls, f, chain):
        return Config.from_dict(yaml.safe_load(f), chain)

    def validate(self):
        pass
