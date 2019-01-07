import json
import time
import logging
import copy
from contractor.deployer import Deployer
from tabulate import tabulate
from termcolor import colored
EXTRA_LOGS_VERBOSITY_CODE = 2


class Watch(object):
    """Watch transactions and user account balance in nectar or ether"""
    def __init__(self, config, network, token, verbosity=1, cumulative=True):
        self.config = config
        self.network = network
        self.token = token
        self.verbosity = verbosity
        self.cumulative = cumulative
        self.poll_interval = 1

        with open('consul/{}.json'.format('ERC20Relay')) as f:
            relay_abi = json.load(f)

        with open('consul/{}.json'.format('BountyRegistry')) as f:
            bounty_abi = json.load(f)

        with open('consul/{}.json'.format('NectarToken')) as f:
            nectar_abi = json.load(f)

        with open('consul/{}.json'.format('ArbiterStaking')) as f:
            staking_abi = json.load(f)

        with open('consul/{}.json'.format(self.network.name)) as f:
            chain_config = json.load(f)

        self.nectarToken = self.network.get_contract(
            nectar_abi['abi'], chain_config['nectar_token_address'])
        self.bountyRegistry = self.network.get_contract(
            bounty_abi['abi'], chain_config['bounty_registry_address'])
        self.erc20Relay = self.network.get_contract(
            relay_abi['abi'], chain_config['erc20_relay_address'])
        self.arbiterStaking = self.network.get_contract(
            staking_abi['abi'], chain_config['arbiter_staking_address'])
        self.contract_map = {
            self.nectarToken.address: self.nectarToken,
            self.bountyRegistry.address: self.bountyRegistry,
            self.erc20Relay.address: self.erc20Relay,
            self.arbiterStaking.address: self.arbiterStaking
        }

    def prettyFormatter(self, old_balances, new_balances):
        if old_balances is None:
            return ""

        users = sorted(old_balances.keys())
        tabulate_list = []

        for user in users:
            old_balnace = old_balances[user]["accounts"][self.token]
            new_balance = new_balances[user]["accounts"][self.token]
            function_calls = new_balances[user]["function_calls"]
            diff = new_balance - old_balnace

            if diff < 0:
                red = 'red'
                formated_new_balance = colored(new_balance, red)
                formated_diff = colored(diff, red)
                tabulate_list.append([user, formated_new_balance, formated_diff, function_calls])
            elif diff > 0:
                green = 'green'
                formated_new_balance = colored(new_balance, green)
                formated_diff = colored(diff, green)
                tabulate_list.append([user, formated_new_balance, formated_diff, function_calls])
            else:
                tabulate_list.append([user, new_balance, diff, function_calls])

        balance_column_label = 'Balance ({})'.format(self.token)
        change_column_label = 'Change {}'.format('(cumulative)' if self.cumulative else '')
        fn_calls_column_label = 'Function Calls {}'.format('(cumulative)' if self.cumulative else '')
        headers = ['User', balance_column_label, change_column_label, fn_calls_column_label]
        return tabulate(tabulate_list, headers=headers)

    def get_address_labels(self):
        address_to_label = dict()
        all_users = self.config.default_contract_config['NectarToken']['users']
        bounty_users = self.config.default_contract_config['BountyRegistry']
        relay_users = self.config.default_contract_config['ERC20Relay']

        for user in all_users:
            shortened_address = user[:7]
            if user in bounty_users['arbiters']:
                address_to_label[user] = 'Abiter {}'.format(shortened_address)
            elif user in relay_users['fee_wallet']:
                address_to_label[user] = 'Fee Wallet {}'.format(shortened_address)
            elif user in relay_users['verifiers']:
                address_to_label[user] = 'Verifier {}'.format(shortened_address)
            else:
                address_to_label[user] = 'User {}'.format(shortened_address)

        address_to_label[self.nectarToken.address] = 'NectarToken'
        address_to_label[self.bountyRegistry.address] = 'BountyRegistry'
        address_to_label[self.erc20Relay.address] = 'ERC20Relay'
        address_to_label[self.arbiterStaking.address] = 'ArbiterStaking'

        return address_to_label

    def watch(self):
        address_to_label = self.get_address_labels()
        last_user_data = dict()
        latest_user_data = dict()
        init_user_data = None
        last_block = None
        block_event_filter = self.network.latest_block_filter()
        while True:
            for event in block_event_filter.get_new_entries():
                latest = self.network.latest_block()

                # skip block if no transactions
                if len(latest['transactions']) == 0:
                    continue

                if self.verbosity == EXTRA_LOGS_VERBOSITY_CODE:
                    logging.info(latest)

                block_number = latest['number']
                logging.info('Block Number: {}'.format(block_number))
                logging.info('Number of transactions: {}'.format(len(latest['transactions'])))

                if not self.cumulative:
                    latest_user_data = dict()

                txs = self.network.get_transactions(latest['transactions'])

                # get and count function calls related to transactions in block
                for tx in txs:
                    if self.verbosity == EXTRA_LOGS_VERBOSITY_CODE:
                        logging.info(tx)
                    if tx.to in self.contract_map:
                        decoded = self.contract_map[tx.to].decode_function_input(tx.input)
                        if self.verbosity == EXTRA_LOGS_VERBOSITY_CODE:
                            logging.info("Decoded Input:")
                            logging.info(decoded)

                        fn = decoded[0].fn_name

                        sender = address_to_label[tx['from']] if tx['from'] in address_to_label else tx['from']
                        if sender not in latest_user_data:
                            latest_user_data[sender] = {"function_calls": dict(), "accounts": dict()}

                        if fn in latest_user_data[sender]["function_calls"]:
                            latest_user_data[sender]["function_calls"][fn] += 1
                        else:
                            latest_user_data[sender]["function_calls"][fn] = 1
                    else:
                        logging.info("Transaction {} outside PolySwarm network, ignoring...", tx.hash)
                        continue

                # get account balances for contracts and users
                for address in list(address_to_label.keys()) + list(self.contract_map.keys()):
                    address_label = address_to_label[address] if address in address_to_label else address
                    if address_label not in latest_user_data:
                        latest_user_data[address_label] = {"function_calls": dict(), "accounts": dict()}

                    if self.token == 'nectar':
                        nectar_balance = self.nectarToken.functions.balanceOf(address).call(block_identifier=block_number)
                        latest_user_data[address_label]["accounts"]['nectar'] = nectar_balance
                    else:
                        ether_balnace = self.network.balance(address, block_identifier=block_number)
                        latest_user_data[address_label]["accounts"]['ether'] = ether_balnace

                if last_block != block_number:
                    # if we want cumulative counts compare `init_user_data` to the lastest account data
                    # else compare to the last block's account data
                    user_compare_data = last_user_data if not self.cumulative else init_user_data
                    logging.info("\n" + self.prettyFormatter(user_compare_data, latest_user_data))

                last_user_data = latest_user_data
                last_block = block_number
                if init_user_data is None:
                    init_user_data = copy.deepcopy(latest_user_data)

            time.sleep(self.poll_interval)
