import logging

from contractor.steps import Step
from contractor.network import Chain
from itertools import zip_longest

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'NectarToken'
MINT_STRIDE = 10


def mint_for_users(network, deployer, users, mint_amount):
    """Mint tokens for a set of users.

    :param network: Network being deployed to
    :param deployer: Deployer for deploying and transacting with contracts
    :param users: Users to mint tokens for
    :param mint_amount: Amount of tokens to mint
    :return: None
    """
    # Take mint requests MINT_STRIDE users at a time
    for i, group in enumerate(zip_longest(*(iter(users),) * MINT_STRIDE)):
        group = filter(None, group)
        txhashes = []
        for j, user in enumerate(group):
            logger.info('Minting %s tokens for user %s: %s', mint_amount, i * MINT_STRIDE + j, user)
            txhashes.append(deployer.transact(deployer.contracts['NectarToken'].functions.mint(user, mint_amount)))

        network.wait_and_check_transactions(txhashes)


class NectarToken(Step):
    """Deployment steps for the NectarToken contract.
    """
    DEACTIVATE_DEPENDENCIES = {'BountyRegistry'}

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        mint = contract_config.get('mint', True)
        users = [network.normalize_address(a) for a in contract_config.get('users', [])]
        user_mint_amount = contract_config.get('mint_amount', 3000000 * 10 ** 18)
        arbiters = [network.normalize_address(a) for a in contract_config.get('arbiters', [])]
        arbiter_mint_amount = contract_config.get('mint_amount', 50000000 * 10 ** 18)

        address = None
        if network.chain == Chain.HOMECHAIN:
            address = network.normalize_address(contract_config.get('home_address'))
        elif network.chain == Chain.SIDECHAIN:
            address = network.normalize_address(contract_config.get('side_address'))

        if address and network.is_contract(address):
            logger.warning('Using already deployed contract for network %s at %s', network.name, address)
            deployer.at(CONTRACT_NAME, address)
        else:
            deployer.deploy(CONTRACT_NAME)

            txhash = deployer.transact(deployer.contracts['NectarToken'].functions.enableTransfers())
            network.wait_and_check_transaction(txhash)

        if mint and network.chain == Chain.HOMECHAIN:
            mint_for_users(network, deployer, users, user_mint_amount)
            mint_for_users(network, deployer, arbiters, arbiter_mint_amount)

    def deactivate(self, network, deployer):
        txhash = deployer.contracts['NectarToken'].functions.pause()
        network.wait_and_check_transaction(txhash)
