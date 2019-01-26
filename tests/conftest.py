import os
import shutil
import tempfile
from collections import namedtuple

import pytest
from eth_account import Account
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from contractor import steps
from contractor.compiler import DEFAULT_SOLC_VERSION
from contractor.compiler import compile_directory
from contractor.deployer import Deployer
from contractor.network import Chain, Network

GAS_LIMIT = 10000000


class TestAccount(object):
    def __init__(self, eth_tester):
        self.priv_key = Account.create().privateKey
        self.address = eth_tester.add_account(self.priv_key.hex())


class TestContract(object):
    def __init__(self):
        self.contract = None

    def bind(self, contract):
        self.contract = contract

    def config(self, chain):
        return {}

    def constructor(self, *args, **kwargs):
        return self.contract.constructor(*args, **kwargs)

    @property
    def address(self):
        return self.contract.address

    @property
    def functions(self):
        return self.contract.functions

    @property
    def events(self):
        return self.contract.events


class NectarToken(TestContract):
    def __init__(self, users):
        super().__init__()
        self.users = users

    def config(self, chain):
        return {'users': [u.address for u in self.users]}


class BountyRegistry(TestContract):
    def __init__(self, nectar_token, ambassadors, experts, arbiters):
        super().__init__()
        self.nectar_token = nectar_token
        self.ambassadors = ambassadors
        self.experts = experts
        self.arbiters = arbiters

    def config(self, chain):
        return {'arbiters': [a.address for a in self.arbiters]}


class ArbiterStaking(TestContract):
    def __init__(self, nectar_token, bounty_registry, arbiter):
        super().__init__()
        self.nectar_token = nectar_token
        self.bounty_registry = bounty_registry
        self.arbiter = arbiter

    def config(self, chain):
        return {'stake_duration': 100}


class ERC20Relay(TestContract):
    def __init__(self, nectar_token, fee_wallet, users, verifiers, verifier_manager, fee_manager):
        super().__init__()
        self.nectar_token = nectar_token
        self.fee_wallet = fee_wallet
        self.users = users
        self.verifiers = verifiers
        self.verifier_manager = verifier_manager
        self.fee_manager = fee_manager

    def config(self, chain):
        return {'stake_duration': 100}


@pytest.fixture(scope='session')
def artifacts():
    basedir = os.path.join(os.path.dirname(__file__), '..')
    srcdir = os.path.join(basedir, 'contracts')
    extdir = os.path.join(basedir, 'external')
    outdir = tempfile.mkdtemp()

    compile_directory(DEFAULT_SOLC_VERSION, srcdir, outdir, extdir)

    yield outdir

    shutil.rmtree(outdir)


@pytest.fixture
def eth_tester():
    # Calls private method on PyEVMBackend but apparently this is the proper way to do this
    genesis = PyEVMBackend._generate_genesis_params({'gas_limit': GAS_LIMIT})
    return EthereumTester(PyEVMBackend(genesis_parameters=genesis))


@pytest.fixture
def web3(eth_tester):
    provider = EthereumTesterProvider(eth_tester)
    return Web3(provider)


def deploy(config, chain, artifacts, eth_tester, web3):
    owner = TestAccount(eth_tester)
    name = 'homechain' if chain == Chain.HOMECHAIN else 'sidechain'
    network = Network.from_web3(name, web3, owner.priv_key, GAS_LIMIT, 0, 10, config, chain)
    deployer = Deployer('test', network, artifacts)
    steps.run(network, deployer, to_deploy=config.keys())

    return (network, deployer)


@pytest.fixture
def bounty_registry(artifacts, eth_tester, web3):
    chain = Chain.SIDECHAIN
    ambassadors = [TestAccount(eth_tester) for _ in range(3)]
    experts = [TestAccount(eth_tester) for _ in range(2)]
    arbiters = [TestAccount(eth_tester) for _ in range(4)]

    users = ambassadors + experts + arbiters
    nectar_token = NectarToken(users)
    bounty_registry = BountyRegistry(nectar_token, ambassadors, experts, arbiters)

    config = {
        'NectarToken': nectar_token.config(chain),
        'BountyRegistry': bounty_registry.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    bounty_registry.bind(deployer.contracts['BountyRegistry'])

    BountyRegistryFixture = namedtuple('BountyRegistryFixture',
                                       ('network', 'deployer', 'NectarToken', 'BountyRegistry'))
    return BountyRegistryFixture(network, deployer, nectar_token, bounty_registry)


@pytest.fixture
def arbiter_staking(artifacts, eth_tester, web3):
    chain = Chain.SIDECHAIN
    arbiter = TestAccount(eth_tester)

    nectar_token = NectarToken([arbiter])
    bounty_registry = BountyRegistry(nectar_token, [], [], [arbiter])
    arbiter_staking = ArbiterStaking(nectar_token, bounty_registry, arbiter)

    config = {
        'NectarToken': nectar_token.config(chain),
        'BountyRegistry': bounty_registry.config(chain),
        'ArbiterStaking': arbiter_staking.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    bounty_registry.bind(deployer.contracts['BountyRegistry'])
    arbiter_staking.bind(deployer.contracts['ArbiterStaking'])

    ArbiterStakingFixture = namedtuple('ArbiterStakingFixture',
                                       ('network', 'deployer', 'NectarToken', 'BountyRegistry', 'ArbiterStaking'))
    return ArbiterStakingFixture(network, deployer, nectar_token, bounty_registry, arbiter_staking)


@pytest.fixture
def erc20_relay(artifacts, eth_tester, web3):
    chain = Chain.SIDECHAIN
    fee_wallet = TestAccount(eth_tester)
    users = [TestAccount(eth_tester) for _ in range(2)]
    verifiers = [TestAccount(eth_tester) for _ in range(3)]
    verifier_manager = TestAccount(eth_tester)
    fee_manager = TestAccount(eth_tester)

    nectar_token = NectarToken(users + verifiers + [fee_wallet, verifier_manager, fee_manager])
    erc20_relay = ERC20Relay(nectar_token, fee_wallet, users, verifiers, verifier_manager, fee_manager)

    config = {
        'NectarToken': nectar_token.config(chain),
        'ERC20Relay': erc20_relay.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    erc20_relay.bind(deployer.contracts['ERC20Relay'])

    ERC20RelayFixture = namedtuple('ERC20RelayFixture',
                                   ('network', 'deployer', 'NectarToken', 'ERC20Relay'))
    return ERC20RelayFixture(network, deployer, nectar_token, erc20_relay)
