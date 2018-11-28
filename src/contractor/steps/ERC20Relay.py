import logging

from contractor.steps import Step
from contractor.config import Chain

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ERC20Relay'
# https://etherscan.io/token/0x9e46a38f5daabe8683e10793b06749eef7d733d1#readContract totalSupply
TOTAL_SUPPLY = 1885913075851542181982426285
# https://coinmarketcap.com/currencies/polyswarm/ retrieved on 5/28/18
NCT_ETH_EXCHANGE_RATE = 80972


class ERC20Relay(Step):
    DEPENDENCIES = {'NectarToken'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        nct_eth_exchange_rate = contract_config.get('nct_eth_exchange_rate', NCT_ETH_EXCHANGE_RATE)
        fee_wallet = contract_config.get('fee_wallet')
        verifiers = [network.w3.toChecksumAddress(addr) for addr in contract_config.get('verifiers')]

        contract = deployer.deploy(CONTRACT_NAME, nectar_token_address, nct_eth_exchange_rate, fee_wallet, verifiers)

        if network.chain == Chain.HOMECHAIN:
            logger.info('Chain is homechain, nothing more to do')
        elif network.chain == Chain.SIDECHAIN:
            logger.info('Minting NCT equal to total supply to relay contract %s on sidechain', contract.address)
            txhash = deployer.transact(deployer.contracts['NectarToken'].functions.mint(contract.address, TOTAL_SUPPLY))
            network.wait_for_transaction(txhash)

    def validate(self, network):
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        fee_wallet = contract_config.get('fee_wallet')
        verifiers = contract_config.get('verifiers')

        return fee_wallet is not None and verifiers is not None
