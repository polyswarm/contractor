import logging
import string
import time
from enum import Enum

import rlp
import trezorlib.ethereum as trezoreth
from eth_account import Account
from eth_utils import is_checksum_address, to_checksum_address
from ethereum.transactions import Transaction
from hexbytes import HexBytes
from trezorlib.client import TrezorClient
from trezorlib.tools import parse_path
from trezorlib.transport import enumerate_devices, get_transport
from trezorlib.ui import ClickUI
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

BLOCKS_TO_WAIT = 5
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'


class Chain(Enum):
    """Different chains we are configured to deploy to.
    """

    HOMECHAIN = 1
    SIDECHAIN = 2

    @staticmethod
    def from_str(s):
        """Construct a Chain from it's string representation.

        :param s: String representation of a chain
        :return: Chain based on provided string
        """
        if s.lower() == 'home':
            return Chain.HOMECHAIN
        elif s.lower() == 'side':
            return Chain.SIDECHAIN
        else:
            raise ValueError('Chain must be either home or side')


class Network(object):
    """Class for interacting with an Ethereum network.
    """

    def __init__(self, name, eth_uri, network_id, gas_limit, gas_price, gas_estimate_multiplier, timeout,
                 contract_config, chain):
        """Create a new network.

        :param name: Name of the network
        :param eth_uri: URI of HTTP RPC endpoint to access network from
        :param network_id: Network ID of the network
        :param gas_limit: Upper bound for gas limit on this network
        :param gas_price: Gas price to use for this network
        :param gas_estimate_multiplier: Amount to scale gas estimates by for this network
        :param timeout: Timeout for RPC calls on this network
        :param contract_config: Configuration for contracts on this network
        :param chain: Is this network the homechain or sidechain for this deployment
        """
        self.name = name
        self.eth_uri = eth_uri
        self.network_id = network_id
        self.gas_limit = gas_limit
        self.gas_price = gas_price
        self.gas_estimate_multiplier = gas_estimate_multiplier
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
    def from_web3(cls, name, w3, priv_key, gas_limit, gas_price, gas_estimate_multiplier, timeout, contract_config,
                  chain):
        """Construct a network based on an already-configured Web3 instance.

        :param name: Name of the network
        :param w3: Web3 instance for interacting with this network
        :param priv_key: Private key used to interact with this network
        :param gas_limit: Upper bound for gas limit on this network
        :param gas_price: Gas price to use for this network
        :param gas_estimate_multiplier: Amount to scale gas estimates by for this network
        :param timeout: Timeout for RPC calls on this network
        :param contract_config: Configuration for contracts on this network
        :param chain: Is this network the homechain or sidechain for this deployment
        :return: New network based on provided Web3 instance
        """
        ret = cls(name, None, None, gas_limit, gas_price, gas_estimate_multiplier, timeout, contract_config, chain)
        ret.w3 = w3
        ret.priv_key = priv_key
        ret.address = w3.eth.account.privateKeyToAccount(priv_key).address
        return ret

    def connect(self, skip_checks=False):
        """Connect to the network.

        :param skip_checks: Skip sanity checks to ensure network is reachable and healthy
        :return: None
        """
        self.w3 = Web3(HTTPProvider(self.eth_uri))
        self.w3.middleware_stack.inject(geth_poa_middleware, layer=0)

        logger.info('Connected to ethereum client at %s, network id: %s', self.eth_uri, self.w3.version.network)

        if not skip_checks:
            self.__preflight_checks()

    def unlock_trezor(self, device_path, derivation_path):
        """Unlock a Trezor for signing transactions to this network.

        :param device_path: Device path of the Trezor
        :param derivation_path: Derivation path of the key to use
        :return: True if success, else False
        """
        try:
            device = get_transport(device_path, prefix_search=False)
        except Exception:
            try:
                device = get_transport(device_path, prefix_search=True)
            except Exception:
                logger.exception('Failed to find Trezor device on path %s', device_path)
                return False

        self.trezor = TrezorClient(transport=device, ui=ClickUI())

        self.address_n = parse_path(derivation_path)
        self.address = self.normalize_address(trezoreth.get_address(self.trezor, self.address_n).hex())
        return True

    def unlock_keyfile(self, keyfile, password):
        """Unlock a JSON keyfile for signing transactions to this network.

        :param keyfile: Keyfile to unlock
        :param password: Password to decrypt keyfile
        :return: True if success, else False
        """
        try:
            self.priv_key = Account.decrypt(keyfile.read(), password)
            self.address = Account.privateKeyToAccount(self.priv_key).address
        except ValueError:
            logger.exception('Incorrect password for keyfile')
            return False

        return True

    def __preflight_checks(self):
        """Perform some sanity checks and retrieve account's current nonce after connecting to a network.

        :return: None
        """
        logger.info('Using address: %s', self.address)

        if self.network_id != int(self.w3.version.network):
            raise Exception('Connected to network with incorrect network id')

        cur_block = start_block = self.w3.eth.blockNumber
        
        if self.chain == Chain.SIDECHAIN:
            cur_block = self.w3.eth.blockNumber
        else:
            while cur_block < BLOCKS_TO_WAIT or cur_block - start_block < BLOCKS_TO_WAIT:
                logger.info('Waiting for blocks to advance')
                time.sleep(1)

                cur_block = self.w3.eth.blockNumber

        while self.w3.eth.getBlock('latest').gasLimit < self.gas_limit:
            logger.info('Waiting for block gas limit to increase to minimum')
            time.sleep(1)

        self.nonce = self.__get_nonce()

    def __get_nonce(self):
        """Retrieve account's current nonce.

        :return: Current nonce for account
        """
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
        """Normalize an Ethereum address into a canonical form

        :param addr: Address to normalize
        :return: Normalized address
        """
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
        """Determine if an address is a contract or not.

        :param addr: Address to check
        :return: True if address is a contract, else False
        """
        return self.w3.eth.getCode(addr) != '0x'

    def txopts(self, increment_nonce=True):
        """Default transaction options for this network.

        :param increment_nonce: Should we increment our nonce after fetching our options
        :return: Default transaction options for this network
        """
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
        """Sign a provided transaction, either with our private key or a Trezor hardware wallet.

        :param tx: Transaction to sign
        :return: Signed transaction
        """
        logger.info('Signing transaction: %s', tx)
        if self.trezor is not None:
            chain_id = tx['chainId']
            txobj = Transaction(
                nonce=tx['nonce'],
                gasprice=tx['gasPrice'],
                startgas=tx['gas'],
                to=tx['to'],
                value=tx['value'],
                data=bytes.fromhex(tx['data'][2:]),
            )

            v, r, s = trezoreth.sign_tx(
                self.trezor,
                n=self.address_n,
                nonce=txobj.nonce,
                gas_price=txobj.gasprice,
                gas_limit=txobj.startgas,
                to=txobj.to,
                value=txobj.value,
                data=txobj.data,
                chain_id=chain_id,
            )

            r = int.from_bytes(r, byteorder='big')
            s = int.from_bytes(s, byteorder='big')

            return rlp.encode(txobj.copy(v=v, r=r, s=s))
        else:
            return self.w3.eth.account.signTransaction(tx, self.priv_key).rawTransaction

    def send_transaction(self, signed_tx):
        """Transmit a signed transaction to the network.

        :param signed_tx: Transaction to send
        :return: Transaction hash of the transmitted transaction
        """
        try:
            txhash = self.w3.eth.sendRawTransaction(signed_tx)
        except ValueError as e:
            if str(e).find("known transaction") != -1:
                txhash = signed_tx.hash
                logger.warning("Got known transaction error for tx %s", txhash.hex())
            else:
                raise e

        logger.info('Submitting tx %s', txhash.hex())
        return txhash

    def block_number(self):
        """Get current block number on this network.

        :return: Current block number on this network
        """
        return self.w3.eth.blockNumber

    def wait_for_transaction(self, txhash):
        """Wait for a transaction to be mined (blocking).

        :param txhash: Transaction hash to wait on
        :return: Transaction receipt for the provided transaction hash
        """
        return self.w3.eth.waitForTransactionReceipt(HexBytes(txhash), timeout=self.timeout)

    def wait_for_transactions(self, txhashes):
        """Wait for multiple transactions to be mined (blocking).

        :param txhashes: Transaction hashes to wait on
        :return: Transaction receipts for the provided transaction hashes
        """
        # TODO: asyncio-ify operations and use asyncio.gather or similar, using blocking API for now
        ret = []
        for txhash in txhashes:
            ret.append(self.wait_for_transaction(txhash))
        return ret

    def check_transaction(self, txhash):
        """Check that a transaction succeeded.

        :param txhash: Transaction hash to check
        :return: True if transaction succeeded, else False
        """
        txhash = HexBytes(txhash)
        tx = self.w3.eth.getTransaction(txhash)
        receipt = self.w3.eth.getTransactionReceipt(txhash)

        logger.info('Receipt for %s: %s', txhash.hex(), dict(receipt))
        return receipt is not None and receipt['gasUsed'] < tx['gas'] and receipt['status'] == 1

    def check_transactions(self, txhashes):
        """Check that multiple transactions succeeded.

        :param txhashes: Transaction hashes to check
        :return: True if all transactions succeeded, else False
        """
        return all([self.check_transaction(txhash) for txhash in txhashes])

    def wait_and_check_transaction(self, txhash):
        """Wait for a transaction to be mined, then check if it succeeded (blocking).

        :param txhash: Transaction hash to wait on and check
        :return: Receipt if transaction succeeded
        """
        txhash = HexBytes(txhash)
        receipt = self.wait_for_transaction(txhash)
        if not self.check_transaction(txhash):
            raise Exception('Transaction {0} failed, check network state'.format(txhash.hex()))
        return receipt

    def wait_and_check_transactions(self, txhashes):
        """Wait for multiple transaction to be mined, then check if they succeeded (blocking).

        :param txhashes: Transaction hashes to wait on and check
        :return: Receipts if transaction succeeded
        """
        receipts = self.wait_for_transactions(txhashes)
        if not self.check_transactions(txhashes):
            raise Exception('Transaction failed, check network state')
        return receipts

    def wait_and_process_receipt(self, txhash, event):
        """Wait for a transaction to be mined, and then process the receipt for events (blocking).

        :param txhash: Transaction hash to wait on
        :param event: Event to check for
        :return: Events fired by transaction
        """
        receipt = self.wait_and_check_transaction(txhash)
        return event.processReceipt(receipt)
