import logging

from contractor.steps import Step
from contractor.network import Chain, ZERO_ADDRESS

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ERC20Relay'
# https://etherscan.io/token/0x9e46a38f5daabe8683e10793b06749eef7d733d1#readContract totalSupply
DEFAULT_TOTAL_SUPPLY = 1885913075851542181982426285
# https://coinmarketcap.com/currencies/polyswarm/ retrieved on 5/28/18
NCT_ETH_EXCHANGE_RATE = 80972


class ERC20Relay(Step):
    """Deployment steps for the ERC20Relay contract.
    """

    DEACTIVATE_DEPENDENCIES = {'BountyRegistry'}
    DEPENDENCIES = {'NectarToken'}
    """ERC20Relay depends on NectarToken"""

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        nct_eth_exchange_rate = contract_config.get('nct_eth_exchange_rate', NCT_ETH_EXCHANGE_RATE)
        fee_wallet = network.normalize_address(contract_config.get('fee_wallet'))
        fee_manager = contract_config.get('fee_manager', None)
        verifiers = [network.normalize_address(a) for a in contract_config.get('verifiers')]

        # Need to mint tokens on the sidechain for the relay contract equal to homechain total supply
        nectar_config = network.contract_config.get('NectarToken', {})
        mint = nectar_config.get('mint', True)
        if mint:
            mint_amount = nectar_config.get('mint_amount', 1000000000 * 10 ** 18)
            users = nectar_config.get('users', [])

            total_supply = mint_amount * len(users)
        else:
            total_supply = nectar_config.get('total_supply', DEFAULT_TOTAL_SUPPLY)

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
            txhash = deployer.transact(deployer.contracts['NectarToken'].functions.mint(contract.address, total_supply))
            network.wait_and_check_transaction(txhash)

        if fee_manager is not None:
            fee_manager = network.normalize_address(fee_manager)
            txhash = deployer.transact(deployer.contracts['ERC20Relay'].functions.setFeeManager(fee_manager))
            network.wait_and_check_transaction(txhash)

    def deactivate(self, network, deployer):
        """Run this deactivate setep

        :param network: Network being deployed to
        :param deployer: deployer for deprecating and transacting resolving in progress tasks
        :return: None
        """
        # Wait until the vote window closed (BountyRegistry already waited on others)
        voteWindow = deployer.contracts['BountyRegistry'].functions.arbiterVoteWindow().call()
        network.wait_for_blocks(int(voteWindow * 1.2))

        # Trigger flush
        txhash = deployer.transact(deployer.contracts['ERC20Relay'].functions.flush())
        network.wait_and_check_transaction(txhash)

    def validate(self, network, deactivate=False):
        """Ensures prerequisites for step and configuration are correct before proceeding.

        :param network: Network being deployed to
        :param deactivate: Is this deactivating, or running
        :return: True if valid, else False
        """
        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        fee_wallet = contract_config.get('fee_wallet')
        verifiers = contract_config.get('verifiers')

        return deactivate or (fee_wallet is not None and verifiers is not None)
