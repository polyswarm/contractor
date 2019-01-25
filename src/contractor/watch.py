import copy
import logging
import time

from colorama import Fore, Style
from tabulate import tabulate

logger = logging.getLogger(__name__)


def colorize(s, color):
    return color + s + Style.RESET_ALL


class Watch(object):
    """Watch transactions and user account balance in nectar or ether"""

    def __init__(self, config, network, deployer, token, cumulative=True, verbosity=1):
        self.config = config
        self.network = network
        self.deployer = deployer
        self.token = token
        self.cumulative = cumulative
        self.verbosity = verbosity
        self.poll_interval = 1

    def tabulate_balances(self, old_balances, new_balances):
        if old_balances is None:
            return ''

        balance_column_label = 'Balance ({})'.format(self.token)
        change_column_label = 'Change {}'.format('(cumulative)' if self.cumulative else '')
        fn_calls_column_label = 'Function Calls {}'.format('(cumulative)' if self.cumulative else '')
        headers = ['User', balance_column_label, change_column_label, fn_calls_column_label]

        users = sorted(old_balances.keys())
        tabulate_list = []
        for user in users:
            old_balance = old_balances[user]['accounts'][self.token]
            new_balance = new_balances[user]['accounts'][self.token]
            function_calls = new_balances[user]['function_calls']
            diff = new_balance - old_balance

            color = Fore.RED if diff < 0 else Fore.GREEN if diff > 0 else Fore.RESET
            tabulate_list.append([user, colorize(new_balance, color), colorize(diff, color), function_calls])

        return tabulate(tabulate_list, headers=headers)

    def get_address_labels(self):
        address_to_label = {}

        nectar_token_config = self.network.contract_config.get('NectarToken', {})
        bounty_registry_config = self.network.contract_config.get('BountyRegistry', {})
        erc20_relay_config = self.config.default_contract_config.get('ERC20Relay', {})
        all_users = nectar_token_config.get('users', [])

        for user in all_users:
            shortened_address = user[:7]
            if user in bounty_registry_config['arbiters']:
                address_to_label[user] = 'Arbiter {}'.format(shortened_address)
            elif user in erc20_relay_config['fee_wallet']:
                address_to_label[user] = 'Fee Wallet {}'.format(shortened_address)
            elif user in erc20_relay_config['verifiers']:
                address_to_label[user] = 'Verifier {}'.format(shortened_address)
            else:
                address_to_label[user] = 'User {}'.format(shortened_address)

        for name, contract in self.deployer.contracts.items():
            address_to_label[contract.address] = name

        return address_to_label

    def watch(self):
        address_to_label = self.get_address_labels()
        contract_map = {contract.address: contract for contract in self.deployer.contracts.values()}

        last_user_data = {}
        latest_user_data = {}
        init_user_data = None
        last_block = None

        block_event_filter = self.network.w3.eth.filter('latest')
        while True:
            for event in block_event_filter.get_new_entries():
                # XXX: Can we get this from the event?
                logger.info('Event data: %s', event)
                latest = self.network.w3.eth.getBlock('latest')

                # Skip block if no transactions
                if len(latest['transactions']) == 0:
                    continue

                if self.verbosity > 0:
                    logger.info(latest)

                block_number = latest['number']
                logging.info('Block Number: %s', block_number)
                logging.info('Number of transactions: %s', len(latest['transactions']))

                if not self.cumulative:
                    latest_user_data = {}

                txs = [self.network.w3.eth.getTransaction(txhash) for txhash in latest['transactions']]
                for tx in txs:
                    if self.verbosity > 0:
                        logging.info(tx)

                    if tx.to in contract_map:
                        decoded = contract_map[tx.to].decode_function_input(tx.input)
                        if self.verbosity > 0:
                            logging.info('Decoded Input: %s', decoded)

                        fn = decoded[0].fn_name

                        sender = address_to_label[tx['from']] if tx['from'] in address_to_label else tx['from']
                        sender_data = latest_user_data.get(sender, {'function_calls': {}, 'accounts': {}})

                        sender_data['function_calls'][fn] = sender_data['function_calls'].get(fn, 0) + 1
                    else:
                        logging.info('Transaction %s outside PolySwarm network, ignoring...', tx.hash)
                        continue

                # Get account balances for contracts and users
                for address, name in address_to_label.items():
                    address_data = latest_user_data.get(name, {'function_calls': {}, 'accounts': {}})

                    if self.token == 'nectar':
                        nectar_balance = self.deployer.contracts['NectarToken'].functions.balanceOf(address).call(
                            block_identifier=block_number)
                        address_data['accounts']['nectar'] = nectar_balance
                    else:
                        ether_balance = self.network.w3.eth.getBalance(address, block_identifier=block_number)
                        address_data['accounts']['ether'] = ether_balance

                if last_block != block_number:
                    # if we want cumulative counts compare `init_user_data` to the latest account data
                    # else compare to the last block's account data
                    user_compare_data = last_user_data if not self.cumulative else init_user_data
                    logging.info('\n' + self.tabulate_balances(user_compare_data, latest_user_data))

                last_user_data = latest_user_data
                last_block = block_number
                if init_user_data is None:
                    init_user_data = copy.deepcopy(latest_user_data)

            time.sleep(self.poll_interval)
