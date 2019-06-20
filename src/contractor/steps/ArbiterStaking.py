import logging

from contractor.steps import Step
from contractor.network import Chain

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ArbiterStaking'


class ArbiterStaking(Step):
    """Deployment steps for the ArbiterStaking contract.
    """

    DEPENDENCIES = {'NectarToken'}
    """ArbiterStaking depends on NectarToken"""

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        stake_duration = contract_config.get('stake_duration', 100)

        address = None
        if network.chain == Chain.HOMECHAIN:
            address = network.normalize_address(contract_config.get('home_address'))
        elif network.chain == Chain.SIDECHAIN:
            address = network.normalize_address(contract_config.get('side_address'))

        if address and network.is_contract(address):
            logger.warning('Using already deployed contract for network %s at %s', network.name, address)
            deployer.at(CONTRACT_NAME, address)
        else:
            deployer.deploy(CONTRACT_NAME, nectar_token_address, stake_duration)
