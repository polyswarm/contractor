import logging
import yaml

from contractor.network import Network

logger = logging.getLogger(__name__)


class NetworkConfig(object):
    """Configuration for an Ethereum network.
    """

    def __init__(self, name, eth_uri, network_id, gas_limit, gas_price, gas_estimate_multiplier, timeout,
                 contract_config, chain):
        """Create a new network configuration from parts.

        :param name: Name of the network
        :param eth_uri: URI of HTTP RPC endpoint to access network from
        :param network_id: Network ID of the network
        :param gas_limit: Upper bound for gas limit on this network
        :param gas_price: Gas price to use for this network
        :param gas_estimate_multiplier: Amount to scale gas estimates by for this network
        :param timeout: Timeout for RPC calls on this network
        :param contract_config: Configuration for contracts on this network
        :param chain: Is this network the homechain or sidechain for this deployment
        """
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
        """Create a new network configuration from a dictionary.

        :param d: Dictionary containing network configuration
        :param name: Name of the network
        :param default_contract_config: Default contract configuration for all networks
        :param chain: Is this network the homechain or sidechain for this deployment
        :return: New network configuration from provided dictionary
        """
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
        """Validate network parameters for sanity.

        :return: None
        """
        # TODO: What else needs to/can be validated?
        if not self.eth_uri.startswith('http'):
            raise ValueError('Non-http RPC endpoint specified as eth_uri')
        if self.timeout <= 0:
            raise ValueError('Invalid timeout')

    def create(self):
        """Create a Network object based on this configuration

        :return: Network object based on this configuration
        """
        return Network(self.name, self.eth_uri, self.network_id, self.gas_limit, self.gas_price,
                       self.gas_estimate_multiplier, self.timeout, self.contract_config, self.chain)


class Config(object):
    """Global configuration for a series of deployments.
    """

    def __init__(self, network_configs, default_contract_config):
        """Create a new Config from the provided network configurations and contract configurations.

        :param network_configs: Configurations for all networks known to this deployment
        :param default_contract_config: Default contract configurations for this deployment
        """
        self.network_configs = network_configs
        self.default_contract_config = default_contract_config

        self.validate()

    @classmethod
    def from_dict(cls, d, chain):
        """Create a new Config from a dictionary

        :param d: Dictionary containing configuration
        :param chain: Is this deployment for the homechain or sidechain
        :return: New configuration from provided dictionary
        """
        default_contract_config = d.get('contracts', {})
        network_configs = {k: NetworkConfig.from_dict(v, k, default_contract_config, chain) for k, v in
                           d.get('networks', {}).items()}

        return cls(network_configs, default_contract_config)

    @classmethod
    def from_yaml(cls, f, chain):
        """Create a new Config from a YAML file

        :param f: File object containing YAML configuration
        :param chain: Is this deployment for the homechain or sidechain
        :return: New configuration from provided YAML file
        """
        return Config.from_dict(yaml.safe_load(f), chain)

    def validate(self):
        """Validate parameters for sanity

        :return: None
        """
        if not self.network_configs:
            raise ValueError('No networks configured')
