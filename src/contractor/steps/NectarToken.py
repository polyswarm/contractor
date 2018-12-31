import logging

from contractor.steps import Step
from contractor.network import Chain
from itertools import zip_longest

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'NectarToken'
MINT_STRIDE = 10


class NectarToken(Step):
    def run(self, network, deployer):
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        users = [network.normalize_address(a) for a in contract_config.get('users', [])]
        mint = contract_config.get('mint', True)
        mint_amount = contract_config.get('mint_amount', 1000000000 * 10 ** 18)

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
            # Take mint requests MINT_STRIDE users at a time
            for i, group in enumerate(zip_longest(*(iter(users),) * MINT_STRIDE)):
                group = filter(None, group)
                txhashes = []
                for j, user in enumerate(group):
                    logger.info('Minting tokens for user %s: %s', i * MINT_STRIDE + j, user)
                    txhashes.append(
                        deployer.transact(deployer.contracts['NectarToken'].functions.mint(user, mint_amount)))

                network.wait_and_check_transactions(txhashes)
