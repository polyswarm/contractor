import logging
import yaml

from contractor.network import Network

logger = logging.getLogger(__name__)


class NetworkConfig(object):
    def __init__(self, name, eth_uri, network_id, gas_limit, gas_price, gas_estimate_multiplier, timeout,
                 contract_config, chain):
        self.name = name
        self.eth_uri = eth_uri
        self.network_id = network_id
        self.gas_limit = gas_limit
        self.gas_price = gas_price
        self.gas_estimate_multiplier = gas_estimate_multiplier
        self.timeout = timeout
        self.contract_config = contract_config
        self.chain = chain

        self.validate()

    @classmethod
    def from_dict(cls, d, name, default_contract_config, chain):
        eth_uri = d.get('eth_uri')
        network_id = d.get('network_id')
        gas_limit = d.get('gas_limit')
        gas_price = d.get('gas_price')
        gas_estimate_multiplier = d.get('gas_estimate_multiplier', 3)
        timeout = d.get('timeout', 240)

        # Copy default contract config and apply any overrides if applicable
        contract_config = dict(default_contract_config)
        contract_config.update(d.get('contracts', {}))

        return cls(name, eth_uri, network_id, gas_limit, gas_price, gas_estimate_multiplier, timeout, contract_config,
                   chain)

    def validate(self):
        # TODO: What else needs to/can be validated?
        if not self.eth_uri.startswith('http'):
            raise ValueError('Non-http RPC endpoint specified as eth_uri')
        if self.timeout <= 0:
            raise ValueError('Invalid timeout')

    def create(self):
        return Network(self.name, self.eth_uri, self.network_id, self.gas_limit, self.gas_estimate_multiplier,
                       self.gas_price, self.timeout, self.contract_config, self.chain)


class Config(object):
    def __init__(self, network_configs, default_contract_config):
        self.network_configs = network_configs
        self.default_contract_config = default_contract_config

        self.validate()

    @classmethod
    def from_dict(cls, d, chain):
        default_contract_config = d.get('contracts', {})
        network_configs = {k: NetworkConfig.from_dict(v, k, default_contract_config, chain) for k, v in
                           d.get('networks', {}).items()}

        return cls(network_configs, default_contract_config)

    @classmethod
    def from_yaml(cls, f, chain):
        return Config.from_dict(yaml.safe_load(f), chain)

    def validate(self):
        if not self.network_configs:
            raise ValueError('No networks configured')
