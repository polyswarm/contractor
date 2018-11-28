import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ArbiterStaking'
STAKE_DURATIONS = {
    # 4 months in blocks
    'mainnet': 701333,
}

class ArbiterStaking(Step):
    DEPENDENCIES = {'NectarToken'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address
        stake_duration = STAKE_DURATIONS.get(network.name, 100)

        deployer.deploy(CONTRACT_NAME, nectar_token_address, stake_duration)
