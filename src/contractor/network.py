import logging
import string
import time
from enum import Enum

import trezorlib.ethereum as trezoreth
import rlp
from eth_account import Account
from eth_utils import is_checksum_address, to_checksum_address
from ethereum.transactions import Transaction
from trezorlib.client import TrezorClient
from trezorlib.tools import parse_path
from trezorlib.transport import enumerate_devices, get_transport
from trezorlib.ui import ClickUI
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

        self.nonce = 0
        self.w3 = None
        self.address = None
        self.priv_key = None
        self.trezor = None
        self.address_n = None

    @classmethod
    def from_web3(cls, name, w3, priv_key, gas_limit, gas_price, timeout, contract_config, chain):
        ret = cls(name, None, None, gas_limit, gas_price, timeout, contract_config, chain)
        ret.w3 = w3
        ret.priv_key = priv_key
        ret.address = w3.eth.account.privateKeyToAccount(priv_key).address
        return ret

    def connect(self, skip_checks=False):
        self.w3 = Web3(HTTPProvider(self.eth_uri))
        self.w3.middleware_stack.inject(geth_poa_middleware, layer=0)

        logger.info('Connected to ethereum client at %s, network id: %s', self.eth_uri, self.w3.version.network)

        if not skip_checks:
            self.__preflight_checks()

    def unlock_trezor(self, device_path, derivation_path):
        device = None
        try:
            device = get_transport(device_path, prefix_search=False)
        except Exception:
            try:
                device = get_transport(device_path, prefix_search=True)
            except Exception:
                logger.exception('Failed to find Trezor device on path %s', device_path)
                return False

        self.trezor = TrezorClient(transport=device, ui=ClickUI)

        self.address_n = parse_path(derivation_path)
        self.address = self.normalize_address(trezoreth.get_address(self.trezor, self.address_n).hex())
        return True

    def unlock_keyfile(self, keyfile, password):
        try:
            self.priv_key = Account.decrypt(keyfile.read(), password)
            self.address = Account.privateKeyToAccount(self.priv_key).address
        except ValueError:
            logger.exception('Incorrect password for keyfile')
            return False

        return True

    def __preflight_checks(self):
        logger.info('Using address: %s', self.address)

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
        if self.address is None:
            logger.warning('No account set, cannot fetch nonce')
            return

        last_nonce = -1
        while True:
            # Also include transactions in txpool
            nonce = self.w3.eth.getTransactionCount(self.address, 'pending')

            if nonce == last_nonce:
                logger.info('Settled on transaction count %s', nonce)
                break

            last_nonce = nonce
            time.sleep(2)

        return nonce

    def normalize_address(self, addr):
        if addr is None:
            return None

        if addr.startswith('0x'):
            addr = addr[2:]

        lowhexdigits = set(string.hexdigits.lower())
        if all([c in lowhexdigits for c in addr]):
            addr = to_checksum_address(addr)[2:]

        addr = '0x' + addr
        if not is_checksum_address(addr):
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

    def sign_transaction(self, tx):
        logger.info('Signing transaction: %s', tx)
        if self.trezor is not None:
            txobj = rlp.decode(tx, Transaction)
            txobj.v, txobj.r, txobj.s = trezoreth.sign_tx(
                self.trezor,
                n=self.address_n,
                nonce=txobj.nonce,
                gas_price=txobj.gasprice,
                gas_limit=txobj.startgas,
                to=txobj.to,
                value=txobj.value,
                data=txobj.data,
                chain_id=self.network_id,
            )
            return rlp.encode(txobj)
        else:
            return self.w3.eth.account.signTransaction(tx, self.priv_key)

    def send_transaction(self, signed_tx):
        try:
            txhash = self.w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        except ValueError as e:
            if str(e).find("known transaction") != -1:
                txhash = signed_tx.hash
                logger.warn("Got known transaction error for tx %s", txhash.hex())
            else:
                raise e

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

    def wait_and_process_receipt(self, txhash, event):
        receipt = self.wait_and_check_transaction(txhash)
        return event.processReceipt(receipt)
