import logging

from contractor.steps import Step
from contractor.network import Chain

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ERC20Relay'
# https://etherscan.io/token/0x9e46a38f5daabe8683e10793b06749eef7d733d1#readContract totalSupply
TOTAL_SUPPLY = 1885913075851542181982426285
# https://coinmarketcap.com/currencies/polyswarm/ retrieved on 5/28/18
NCT_ETH_EXCHANGE_RATE = 80972
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'


class ERC20Relay(Step):
    DEPENDENCIES = {'NectarToken'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        nct_eth_exchange_rate = contract_config.get('nct_eth_exchange_rate', NCT_ETH_EXCHANGE_RATE)
        fee_wallet = network.normalize_address(contract_config.get('fee_wallet'))
        verifiers = [network.normalize_address(a) for a in contract_config.get('verifiers')]

        address = None
        if network.chain == Chain.HOMECHAIN:
            address = network.normalize_address(contract_config.get('home_address'))
        elif network.chain == Chain.SIDECHAIN:
            address = network.normalize_address(contract_config.get('side_address'))

        if address and network.is_contract(address):
            logger.warning('Using already deployed contract for network %s at %s', network.name, address)
            deployer.at(CONTRACT_NAME, address)
            return

        if network.chain == Chain.HOMECHAIN:
            deployer.deploy(CONTRACT_NAME, nectar_token_address, nct_eth_exchange_rate, fee_wallet, verifiers)
            logger.info('Chain is homechain, nothing more to do')
        elif network.chain == Chain.SIDECHAIN:
            contract = deployer.deploy(CONTRACT_NAME, nectar_token_address, 0, ZERO_ADDRESS, verifiers)

            logger.info('Minting NCT equal to total supply to relay contract %s on sidechain', contract.address)
            txhash = deployer.transact(deployer.contracts['NectarToken'].functions.mint(contract.address, TOTAL_SUPPLY))
            network.wait_and_check_transaction(txhash)

    def validate(self, network):
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        fee_wallet = contract_config.get('fee_wallet')
        verifiers = contract_config.get('verifiers')

        return fee_wallet is not None and verifiers is not None
