import logging
import string
import time
from enum import Enum

from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

BLOCKS_TO_WAIT = 5


class Chain(Enum):
    HOMECHAIN = 1
    SIDECHAIN = 2

    @staticmethod
    def from_str(s):
        if s.lower() == 'home':
            return Chain.HOMECHAIN
        elif s.lower() == 'side':
            return Chain.SIDECHAIN
        else:
            raise ValueError('Chain must be either home or side')


class Network(object):
    def __init__(self, name, eth_uri, network_id, gas_limit, gas_price, timeout, contract_config, chain):
        self.name = name
        self.eth_uri = eth_uri
        self.network_id = network_id
        self.gas_limit = gas_limit
        self.gas_price = gas_price
        self.timeout = timeout
        self.contract_config = contract_config
        self.chain = chain

        self.w3 = Web3(HTTPProvider(self.eth_uri))
        self.w3.middleware_stack.inject(geth_poa_middleware, layer=0)

        self.nonce = 0
        self.priv_key = None
        self.account = None

    def connect(self, keyfile, password):
        self.priv_key = self.w3.eth.account.decrypt(keyfile.read(), password)
        self.account = self.w3.eth.account.privateKeyToAccount(self.priv_key).address

        logger.info('Connected to ethereum client at %s, network id: %s, using account %s', self.eth_uri,
                    self.w3.version.network, self.account)

        self.__preflight_checks()

    def __preflight_checks(self):
        if self.network_id != int(self.w3.version.network):
            raise Exception('Connected to network with incorrect network id')

        cur_block = start_block = self.w3.eth.blockNumber
        while cur_block < BLOCKS_TO_WAIT or cur_block - start_block < BLOCKS_TO_WAIT:
            logger.info('Waiting for blocks to advance')
            time.sleep(1)

            cur_block = self.w3.eth.blockNumber

        while self.w3.eth.getBlock('latest').gasLimit < self.gas_limit:
            logger.info('Waiting for block gas limit to increase to minimum')
            time.sleep(1)

        self.nonce = self.__get_nonce()

    def __get_nonce(self):
        # the following assumes __get_nonce is only called when a tx is actually sent
        
        reported_nonce = self.w3.eth.getTransactionCount(self.account, 'pending')

        if reported_nonce > self.nonce+1:
            nonce = reported_nonce
        else:
            nonce = self.nonce+1

        return nonce

    def normalize_address(self, addr):
        if addr is None:
            return None

        if addr.startswith('0x'):
            addr = addr[2:]

        lowhexdigits = set(string.hexdigits.lower())
        if all([c in lowhexdigits for c in addr]):
            addr = self.w3.toChecksumAddress(addr)[2:]

        addr = '0x' + addr
        if not self.w3.isChecksumAddress(addr):
            raise ValueError('Address is mixed case, but checksum is invalid')

        return addr

    def is_contract(self, addr):
        return self.w3.eth.getCode(addr) != '0x'

    def txopts(self, increment_nonce=True):
        logger.info('Preparing tx with nonce %s', self.nonce)
        ret = {
            # XXX: Difference between these is subtle but irrelevant for our purposes
            'chainId': self.network_id,
            'gas': self.gas_limit,
            'gasPrice': self.gas_price,
            'nonce': self.nonce,
        }

        # XXX: Right now everything is synchronous so we don't need to lock
        if increment_nonce:
            self.nonce += 1

        return ret

    def latest_block(self):
        return self.w3.eth.getBlock('latest')

    def latest_block_filter(self):
        return self.w3.eth.filter('latest')

    def get_transactions(self, list_of_tx_hashes):
        ret = []
        for tx_hash in list_of_tx_hashes:
            tx = self.w3.eth.getTransaction(tx_hash)
            ret.append(tx)
        return ret

    def balance(self, address, block_identifier='latest'):
        return self.w3.eth.getBalance(address, block_identifier)

    def get_contract(self, abi, address):
        return self.w3.eth.contract(abi=abi, address=address)

    def sign_transaction(self, tx):
        logger.info('Signing transaction: %s', tx)
        return self.w3.eth.account.signTransaction(tx, self.priv_key)

    def send_transaction(self, signed_tx):
        txhash = self.w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        logger.info('Submitting tx %s', txhash.hex())
        return txhash

    def block_number(self):
        return self.w3.eth.blockNumber

    def wait_for_transaction(self, txhash):
        return self.w3.eth.waitForTransactionReceipt(txhash, timeout=self.timeout)

    def wait_for_transactions(self, txhashes):
        # TODO: asyncio-ify operations and use asyncio.gather or similar, using blocking API for now
        ret = []
        for txhash in txhashes:
            ret.append(self.wait_for_transaction(txhash))
        return ret

    def check_transaction(self, txhash):
        tx = self.w3.eth.getTransaction(txhash)
        receipt = self.w3.eth.getTransactionReceipt(txhash)

        logger.info('Receipt for %s: %s', txhash.hex(), dict(receipt))
        return receipt is not None and receipt['gasUsed'] < tx['gas'] and receipt['status'] == 1

    def check_transactions(self, txhashes):
        return all([self.check_transaction(txhash) for txhash in txhashes])

    def wait_and_check_transaction(self, txhash):
        receipt = self.wait_for_transaction(txhash)
        if not self.check_transaction(txhash):
            raise Exception('Transaction {0} failed, check network state'.format(txhash.hex()))
        return receipt

    def wait_and_check_transactions(self, txhashes):
        receipts = self.wait_for_transactions(txhashes)
        if not self.check_transactions(txhashes):
            raise Exception('Transaction failed, check network state')
        return receipts
