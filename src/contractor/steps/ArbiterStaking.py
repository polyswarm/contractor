import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ArbiterStaking'

class ArbiterStaking(Step):
    DEPENDENCIES = {'NectarToken'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        stake_duration = contract_config.get('stake_duration', 100)

        deployer.deploy(CONTRACT_NAME, nectar_token_address, stake_duration)
