import click
import pprint
import time
from enum import Enum

from colorama import Fore, Style
from tabulate import tabulate

pp = pprint.PrettyPrinter(indent=2)


class Token(Enum):
    """Types of cryptocurrency we interact with.
    """

    ETHER = 1
    NECTAR = 2

    @staticmethod
    def from_str(s):
        """Construct a Token from it's string representation.

        :param s: String representation of a token
        :return: Token based on provided string
        """
        if s.lower() == 'ether' or s.lower() == 'eth':
            return Token.ETHER
        elif s.lower() == 'nectar' or s.lower() == 'nct':
            return Token.NECTAR
        else:
            raise ValueError('Token must be either ether or nectar')


def colorize(s, color):
    """Format a string using a color

    :param s: String to colorize
    :param color: Color to set
    :return: Formatted string
    """
    return color + str(s) + Style.RESET_ALL


def get_address_labels(network, deployer):
    """Construct friendly labels for known addresses.

    :param network: Network to interact with
    :param deployer: Deployer for interacting with contracts
    :return: Dictionary of addresses to friendly labels
    """
    address_to_label = {}

    nectar_token_config = network.contract_config.get('NectarToken', {})
    bounty_registry_config = network.contract_config.get('BountyRegistry', {})
    erc20_relay_config = network.contract_config.get('ERC20Relay', {})

    users = nectar_token_config.get('users', [])
    for user in users:
        user = network.normalize_address(user)
        address_to_label[user] = 'User {}'.format(user[:7])

    arbiters = bounty_registry_config.get('arbiters', [])
    for user in arbiters:
        user = network.normalize_address(user)
        address_to_label[user] = 'Arbiter {}'.format(user[:7])

    verifiers = erc20_relay_config.get('verifiers')
    for user in verifiers:
        user = network.normalize_address(user)
        address_to_label[user] = 'Verifiers {}'.format(user[:7])

    fee_wallet = erc20_relay_config.get('fee_wallet', None)
    if fee_wallet:
        user = network.normalize_address(fee_wallet)
        address_to_label[user] = 'Fee Wallet{}'.format(user[:7])

    for name, contract in deployer.contracts.items():
        address_to_label[contract.address] = name

    return address_to_label


class User(object):
    """Tracks balances and function calls for an address (representing a user's activity).
    """

    def __init__(self, address, name=None):
        """Construct a new User

        :param address: Address to track
        :param name: Friendly name for this user, if available
        """
        self.address = address
        self.name = name if name is not None else address
        self.function_calls = {}
        self.eth_balance = 0
        self.nct_balance = 0

    def record_function_call(self, fn_name):
        """Record a function call for this user.

        :param fn_name: Name of the function being called
        :return: None
        """
        self.function_calls[fn_name] = self.function_calls.get(fn_name, 0) + 1

    def update_balances(self, network, deployer, block_identifier='latest'):
        """Update balances for a user

        :param network: Network to interact with
        :param deployer: Deployer for interacting with contracts
        :param block_identifier: Block to update for
        :return: None
        """
        address = network.normalize_address(self.address)
        self.eth_balance = network.w3.eth.getBalance(address, block_identifier=block_identifier)
        self.nct_balance = deployer.contracts['NectarToken'].functions.balanceOf(address).call(
            block_identifier=block_identifier)


class Watch(object):
    """Watch transactions and user account balance in Nectar or Ether.
    """

    def __init__(self, config, token, cumulative=True, verbosity=1):
        """Construct a Watch object for monitoring activity in the network.

        :param config: Configuration to use
        :param token: Token to track (Nectar or Ether)
        :param cumulative: Track balances cumulatively or per block
        :param verbosity: How verbose should we log events
        """
        self.config = config
        self.token = token
        self.cumulative = cumulative
        self.verbosity = verbosity
        self.poll_interval = 1

    def tabulate_balances(self, prev_user_data, cur_user_data):
        """Construct a table of updated balances per block.

        :param prev_user_data: Previous data for all users
        :param cur_user_data: Current data for all users
        :return: String containing tabulated balances
        """
        balance_column_label = 'Balance ({})'.format(self.token)
        change_column_label = 'Change {}'.format('(cumulative)' if self.cumulative else '')
        fn_calls_column_label = 'Function Calls {}'.format('(cumulative)' if self.cumulative else '')
        headers = ['User', balance_column_label, change_column_label, fn_calls_column_label]

        users = sorted(prev_user_data.keys())
        tabulate_list = []
        for user in users:
            old_user = prev_user_data.get(user)
            new_user = cur_user_data.get(user, old_user)

            old_balance = old_user.eth_balance if self.token == Token.ETHER else old_user.nct_balance
            new_balance = new_user.eth_balance if self.token == Token.ETHER else new_user.nct_balance

            function_calls = new_user.function_calls
            diff = new_balance - old_balance

            color = Fore.RED if diff < 0 else Fore.GREEN if diff > 0 else Fore.RESET
            tabulate_list.append([user, colorize(new_balance, color), colorize(diff, color), function_calls])

        return tabulate(tabulate_list, headers=headers)

    def watch(self, network, deployer):
        """Start watching events on a network (blocking).

        :param network: Network to interact with
        :param deployer: Deployer for interacting with contracts
        :return: None
        """
        address_to_label = get_address_labels(network, deployer)
        contract_map = {contract.address: contract for contract in deployer.contracts.values()}

        prev_user_data = {}
        last_block = None

        block_event_filter = network.w3.eth.filter('latest')
        while True:
            for _ in block_event_filter.get_new_entries():
                latest = network.w3.eth.getBlock('latest')

                block_number = latest['number']
                if last_block is not None and block_number <= last_block:
                    if self.verbosity > 1:
                        click.echo('Duplicate block, continuing')
                    continue

                cur_user_data = {}
                last_block = block_number
                click.echo('-' * 80)

                click.echo('Block Number: {}'.format(block_number))
                click.echo('Number of transactions: {}'.format(len(latest['transactions'])))

                if len(latest['transactions']) == 0:
                    if self.verbosity > 1:
                        click.echo('Empty block, continuing')
                    continue

                if self.verbosity > 0:
                    click.echo('New block: {}'.format(pp.pformat(dict(latest))))

                # Track function calls for each transaction in this block
                txs = [network.w3.eth.getTransaction(txhash) for txhash in latest['transactions']]
                for tx in txs:
                    if self.verbosity > 1:
                        click.echo('Transaction: {}'.format(pp.pformat(dict(tx))))

                    if tx.input and tx.to in contract_map:
                        decoded = contract_map[tx.to].decode_function_input(tx.input)
                        if self.verbosity > 0:
                            click.echo('Decoded Input: {}'.format(decoded))

                        fn = decoded[0].fn_name
                        address = tx['from']

                        name = address_to_label.get(address, address)
                        user = cur_user_data.get(name, User(address, name))
                        user.record_function_call(fn)
                        cur_user_data[name] = user
                    else:
                        click.echo('Transaction {} outside PolySwarm network, ignoring...'.format(tx.hash))
                        continue

                # Get account balances for all participants
                for address, name in address_to_label.items():
                    user = cur_user_data.get(name, User(address, name))
                    user.update_balances(network, deployer, block_identifier=block_number)
                    cur_user_data[name] = user

                click.echo(self.tabulate_balances(prev_user_data, cur_user_data))

                if not self.cumulative or not prev_user_data:
                    prev_user_data.update(cur_user_data)

            time.sleep(self.poll_interval)
