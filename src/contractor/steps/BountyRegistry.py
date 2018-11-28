import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'BountyRegistry'
ARBITER_VOTE_WINDOWS = {
    # 7 days in blocks
    'mainnet': 40320,
}

class BountyRegistry(Step):
    DEPENDENCIES = {'NectarToken', 'ArbiterStaking'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address
        arbiter_staking_address = deployer.contracts['ArbiterStaking'].address
        arbiter_vote_window = ARBITER_VOTE_WINDOWS.get(network.name, 100)

        contract = deployer.deploy(CONTRACT_NAME, nectar_token_address, arbiter_staking_address, arbiter_vote_window)

        logger.info('Setting ArbiterStaking\'s BountyRegistry instance to %s', contract.address)

        txhash = deployer.transact(deployer.contracts['ArbiterStaking'].functions.setBountyRegistry(contract.address))
        network.wait_for_transaction(txhash)
