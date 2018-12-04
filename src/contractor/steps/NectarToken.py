import logging

from contractor.steps import Step
from itertools import zip_longest

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'NectarToken'
MINT_STRIDE = 10

class NectarToken(Step):
    def run(self, network, deployer):
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        address = contract_config.get('address')
        users = contract_config.get('users', [])
        mint_amount = contract_config.get('mint_amount', 1000000000 * 10 ** 18)

        if address:
            logger.warning('Using already deployed contract for network %s at %s', network.name, address)
            deployer.at(CONTRACT_NAME, address)
        else:
            deployer.deploy(CONTRACT_NAME)

        # Take mint requests MINT_STRIDE users at a time
        for i, group in enumerate(zip_longest(*(iter(users),) * MINT_STRIDE)):
            group = filter(None, group)
            txhashes = []
            for j, user in enumerate(group):
                logger.info('Minting tokens for user %s: %s', i + j, user)
                txhashes.append(deployer.transact(deployer.contracts['NectarToken'].functions.mint(user, mint_amount)))

            network.wait_and_check_transactions(txhashes)
