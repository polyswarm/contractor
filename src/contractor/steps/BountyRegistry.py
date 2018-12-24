import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'BountyRegistry'


class BountyRegistry(Step):
    DEPENDENCIES = {'NectarToken', 'ArbiterStaking'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address
        arbiter_staking_address = deployer.contracts['ArbiterStaking'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        arbiter_vote_window = contract_config.get('arbiter_vote_window', 100)
        arbiters = [network.normalize_address(a) for a in contract_config.get('arbiters', [])]

        contract = deployer.deploy(CONTRACT_NAME, nectar_token_address, arbiter_staking_address, arbiter_vote_window)

        logger.info('Setting ArbiterStaking\'s BountyRegistry instance to %s', contract.address)
        txhash = deployer.transact(deployer.contracts['ArbiterStaking'].functions.setBountyRegistry(contract.address))
        network.wait_and_check_transaction(txhash)

        txhashes = []
        for arbiter in arbiters:
            logger.info('Adding %s as an arbiter', arbiter)
            txhashes.append(deployer.transact(
                deployer.contracts['BountyRegistry'].functions.addArbiter(arbiter, network.block_number())))

        network.wait_and_check_transactions(txhashes)
