import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'BountyRegistry'


class BountyRegistry(Step):
    """Deployment steps for the BountyRegistry contract.
    """

    DEPENDENCIES = {'NectarToken', 'ArbiterStaking'}
    """BountyRegistry depends on NectarToken and ArbiterStaking"""

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address
        arbiter_staking_address = deployer.contracts['ArbiterStaking'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        arbiter_vote_window = contract_config.get('arbiter_vote_window', 100)
        assertion_reveal_window = contract_config.get('assertion_reveal_window', 10)
        arbiters = [network.normalize_address(a) for a in contract_config.get('arbiters', [])]

        contract = deployer.deploy(CONTRACT_NAME,
                                   nectar_token_address,
                                   arbiter_staking_address,
                                   arbiter_vote_window,
                                   assertion_reveal_window)

        logger.info('Setting ArbiterStaking\'s BountyRegistry instance to %s', contract.address)
        txhash = deployer.transact(deployer.contracts['ArbiterStaking'].functions.setBountyRegistry(contract.address))
        network.wait_and_check_transaction(txhash)

        txhashes = []
        for arbiter in arbiters:
            logger.info('Adding %s as an arbiter', arbiter)
            txhashes.append(deployer.transact(
                deployer.contracts['BountyRegistry'].functions.addArbiter(arbiter, network.block_number())))

        network.wait_and_check_transactions(txhashes)

    def deactivate(self, network, deployer):
        """Run this deactivate setep

        :param network: Network being deployed to
        :param deployer: Deployer for tearing down this contract and transacting resolving in progress tasks
        :return: None
        """
        txhash = deployer.transact(deployer.contracts['BountyRegistry'].functions.deprecate())
        network.wait_and_check_transaction(txhash)

        revealWindow = deployer.contracts['BountyRegistry'].functions.assertionRevealWindow.call()
        voteWindow = deployer.contracts['BountyRegistry'].functions.arbiterVoteWindow.call()
        max_duration = deployer.contracts['BountyRegistry'].functions.MAX_DURATION.call()
        network.wait_blocks((revealWindow + voteWindow + max_duration) * 2)
