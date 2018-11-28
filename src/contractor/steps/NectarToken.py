import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'NectarToken'


class NectarToken(Step):
    def run(self, network, deployer):
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        address = contract_config.get('address')

        if address:
            logger.warning('Using already deployed contract for network %s at %s', network.name, address)
            deployer.at(CONTRACT_NAME, address)
        else:
            deployer.deploy(CONTRACT_NAME)
