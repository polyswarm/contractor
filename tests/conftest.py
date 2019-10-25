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

GAS_LIMIT = 7500000
GAS_MULTIPLIER = 3


class TestAccount(object):
    """Encapsulate a random private key added to our eth_tester instance"""

    def __init__(self, eth_tester):
        self.priv_key = Account.create().privateKey
        self.address = eth_tester.add_account(self.priv_key.hex())


class TestContract(object):
    """Encapsulate a tested contract and its associated config"""

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
    def __init__(self, users, arbiters, mint=True):
        super().__init__()
        self.users = users
        self.arbiters = arbiters
        self.mint = mint
        self.owner = None

    def config(self, chain):
        return {
            'users': [u.address for u in self.users],
            'arbiters': [a.address for a in self.arbiters],
            'mint': self.mint
        }


class BountyRegistry(TestContract):
    def __init__(self, nectar_token, stake_amount, arbiter_vote_window, assertion_reveal_window, ambassadors, experts, arbiters, fee_manager,
                 window_manager):
        super().__init__()
        self.nectar_token = nectar_token
        self.stake_amount = stake_amount
        self.arbiter_vote_window = arbiter_vote_window
        self.assertion_reveal_window = assertion_reveal_window
        self.ambassadors = ambassadors
        self.experts = experts
        self.arbiters = arbiters
        self.owner = None
        self.fee_manager = fee_manager
        self.window_manager = window_manager

    def config(self, chain):
        return {
            'arbiters': [a.address for a in self.arbiters],
            'arbiter_vote_window': self.arbiter_vote_window,
            'assertion_reveal_window': self.assertion_reveal_window
        }


class TestBountyRegistryContract(BountyRegistry):
    pass


class TestBountyRegistry(steps.Step):
    DEPENDENCIES = {'NectarToken', 'ArbiterStaking'}

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address
        arbiter_staking_address = deployer.contracts['ArbiterStaking'].address

        contract_config = network.contract_config.get('TestBountyRegistry', {})
        arbiter_vote_window = contract_config.get('arbiter_vote_window', 100)
        assertion_reveal_window = contract_config.get('assertion_reveal_window', 10)
        arbiters = [network.normalize_address(a) for a in contract_config.get('arbiters', [])]

        contract = deployer.deploy('TestBountyRegistry',
                                   nectar_token_address,
                                   arbiter_staking_address,
                                   arbiter_vote_window,
                                   assertion_reveal_window)

        txhash = deployer.transact(
            deployer.contracts['ArbiterStaking'].functions.setBountyRegistry(contract.address))
        network.wait_and_check_transaction(txhash)

        txhashes = []
        for arbiter in arbiters:
            txhashes.append(deployer.transact(
                deployer.contracts['TestBountyRegistry'].functions.addArbiter(arbiter, network.block_number())))

        network.wait_and_check_transactions(txhashes)


class ArbiterStaking(TestContract):
    def __init__(self, nectar_token, bounty_registry, stake_duration, arbiter):
        super().__init__()
        self.nectar_token = nectar_token
        self.bounty_registry = bounty_registry
        self.stake_duration = stake_duration
        self.arbiter = arbiter
        self.owner = None

    def config(self, chain):
        return {'stake_duration': self.stake_duration}


class ERC20Relay(TestContract):
    def __init__(self, nectar_token, fee_wallet, users, verifiers, verifier_manager, fee_manager):
        super().__init__()
        self.nectar_token = nectar_token
        self.fee_wallet = fee_wallet
        self.users = users
        self.verifiers = verifiers
        self.verifier_manager = verifier_manager
        self.fee_manager = fee_manager
        self.owner = None

    def config(self, chain):
        return {'fee_wallet': self.fee_wallet.address, 'verifiers': [v.address for v in self.verifiers]}


@pytest.fixture(scope='session')
def artifacts():
    basedir = os.path.join(os.path.dirname(__file__), '..')
    srcdir = os.path.join(basedir, 'contracts')
    extdir = os.path.join(basedir, 'external')
    testdir = os.path.join(basedir, 'tests', 'contracts')
    outdir = os.path.join(basedir, 'build')

    compile_directory(DEFAULT_SOLC_VERSION, srcdir, outdir, [extdir])
    compile_directory(DEFAULT_SOLC_VERSION, testdir, outdir, [srcdir, extdir])

    yield outdir

    shutil.rmtree(outdir)


@pytest.fixture
def eth_tester():
    # Calls private method on PyEVMBackend but apparently this is the proper way to do this
    genesis = PyEVMBackend._generate_genesis_params({'gas_limit': 2 * GAS_LIMIT})
    return EthereumTester(PyEVMBackend(genesis_parameters=genesis))


@pytest.fixture
def web3(eth_tester):
    def zero_gas_price_middleware(make_request, web3):
        def middleware(method, params):
            if method == 'eth_sendTransaction' or method == 'eth_estimateGas':
                transaction = params[0]
                transaction['gasPrice'] = 0
                return make_request(method, [transaction])

            return make_request(method, params)

        return middleware

    provider = EthereumTesterProvider(eth_tester)
    ret = Web3(provider)
    ret.middleware_stack.inject(zero_gas_price_middleware, layer=0)

    return ret


def deploy(config, chain, artifacts, eth_tester, web3):
    owner = TestAccount(eth_tester)
    name = 'homechain' if chain == Chain.HOMECHAIN else 'sidechain'
    network = Network.from_web3(name, web3, owner.priv_key, GAS_LIMIT, 0, GAS_MULTIPLIER, 10, config, chain)
    deployer = Deployer('test', network, artifacts)
    steps.run(network, deployer, to_deploy=config.keys())

    return (network, deployer)


@pytest.fixture
def nectar_token(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    users = [TestAccount(eth_tester) for _ in range(10)]

    nectar_token = NectarToken(users, [])

    config = {
        'NectarToken': nectar_token.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address

    NectarTokenFixture = namedtuple('NectarTokenFixture', ('network', 'deployer', 'NectarToken'))
    return NectarTokenFixture(network, deployer, nectar_token)


@pytest.fixture
def bounty_registry(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    ambassadors = [TestAccount(eth_tester) for _ in range(3)]
    experts = [TestAccount(eth_tester) for _ in range(2)]
    arbiters = [TestAccount(eth_tester) for _ in range(4)]
    fee_manager = TestAccount(eth_tester)
    window_manager = TestAccount(eth_tester)

    users = ambassadors + experts
    nectar_token = NectarToken(users, arbiters)
    bounty_registry = BountyRegistry(nectar_token, 10000000 * 10 ** 18, 100, 10, ambassadors, experts, arbiters,
                                     fee_manager, window_manager)
    arbiter_staking = ArbiterStaking(nectar_token, bounty_registry, 100, arbiters[0])

    config = {
        'NectarToken': nectar_token.config(chain),
        'BountyRegistry': bounty_registry.config(chain),
        'ArbiterStaking': arbiter_staking.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address
    bounty_registry.bind(deployer.contracts['BountyRegistry'])
    bounty_registry.owner = network.address
    arbiter_staking.bind(deployer.contracts['ArbiterStaking'])
    arbiter_staking.owner = network.address

    # Stake all arbiters to avoid settle div by zero
    for arbiter in arbiters:
        nectar_token.functions.approve(arbiter_staking.address, bounty_registry.stake_amount).transact(
            {'from': arbiter.address})
        arbiter_staking.functions.deposit(bounty_registry.stake_amount).transact({'from': arbiter.address})

    BountyRegistryFixture = namedtuple('BountyRegistryFixture',
                                       ('network', 'deployer', 'NectarToken', 'BountyRegistry', 'ArbiterStaking'))
    return BountyRegistryFixture(network, deployer, nectar_token, bounty_registry, arbiter_staking)


@pytest.fixture
def test_bounty_registry(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    ambassadors = [TestAccount(eth_tester) for _ in range(3)]
    experts = [TestAccount(eth_tester) for _ in range(2)]
    arbiters = [TestAccount(eth_tester) for _ in range(4)]
    fee_manager = TestAccount(eth_tester)
    window_manager = TestAccount(eth_tester)

    users = ambassadors + experts
    nectar_token = NectarToken(users, arbiters)
    test_bounty_registry = TestBountyRegistryContract(nectar_token, 10000000 * 10 ** 18, 100, 10, ambassadors, experts,
                                                      arbiters, fee_manager, window_manager)
    arbiter_staking = ArbiterStaking(nectar_token, test_bounty_registry, 100, arbiters[0])

    config = {
        'NectarToken': nectar_token.config(chain),
        'TestBountyRegistry': test_bounty_registry.config(chain),
        'ArbiterStaking': arbiter_staking.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address
    test_bounty_registry.bind(deployer.contracts['TestBountyRegistry'])
    test_bounty_registry.owner = network.address
    arbiter_staking.bind(deployer.contracts['ArbiterStaking'])
    arbiter_staking.owner = network.address

    # Stake all arbiters to avoid settle div by zero
    for arbiter in arbiters:
        nectar_token.functions.approve(arbiter_staking.address, bounty_registry.stake_amount).transact(
            {'from': arbiter.address})
        arbiter_staking.functions.deposit(bounty_registry.stake_amount).transact({'from': arbiter.address})

    TestBountyRegistryFixture = namedtuple('TestBountyRegistryFixture',
                                           ('network',
                                            'deployer',
                                            'NectarToken',
                                            'TestBountyRegistry',
                                            'ArbiterStaking')
                                           )
    return TestBountyRegistryFixture(network, deployer, nectar_token, test_bounty_registry, arbiter_staking)


@pytest.fixture
def arbiter_staking(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    arbiter = TestAccount(eth_tester)
    fee_manager = TestAccount(eth_tester)
    window_manager = TestAccount(eth_tester)

    nectar_token = NectarToken([], [arbiter])
    bounty_registry = BountyRegistry(nectar_token, 10000000 * 10 ** 18, 100, [], [], [arbiter], fee_manager,
                                     window_manager)
    arbiter_staking = ArbiterStaking(nectar_token, bounty_registry, 100, arbiter)

    config = {
        'NectarToken': nectar_token.config(chain),
        'BountyRegistry': bounty_registry.config(chain),
        'ArbiterStaking': arbiter_staking.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address
    bounty_registry.bind(deployer.contracts['BountyRegistry'])
    bounty_registry.owner = network.address
    arbiter_staking.bind(deployer.contracts['ArbiterStaking'])
    arbiter_staking.owner = network.address

    ArbiterStakingFixture = namedtuple('ArbiterStakingFixture',
                                       ('network', 'deployer', 'NectarToken', 'BountyRegistry', 'ArbiterStaking'))
    return ArbiterStakingFixture(network, deployer, nectar_token, bounty_registry, arbiter_staking)

@pytest.fixture
def arbiter_long_staking(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    arbiter = TestAccount(eth_tester)
    fee_manager = TestAccount(eth_tester)
    window_manager = TestAccount(eth_tester)

    nectar_token = NectarToken([], [arbiter])
    bounty_registry = BountyRegistry(nectar_token, 10000000 * 10 ** 18, 100, [], [], [arbiter], fee_manager,
                                     window_manager)
    arbiter_staking = ArbiterStaking(nectar_token, bounty_registry, 100000, arbiter)

    config = {
        'NectarToken': nectar_token.config(chain),
        'BountyRegistry': bounty_registry.config(chain),
        'ArbiterStaking': arbiter_staking.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address
    bounty_registry.bind(deployer.contracts['BountyRegistry'])
    bounty_registry.owner = network.address
    arbiter_staking.bind(deployer.contracts['ArbiterStaking'])
    arbiter_staking.owner = network.address

    ArbiterStakingFixture = namedtuple('ArbiterStakingFixture',
                                       ('network', 'deployer', 'NectarToken', 'BountyRegistry', 'ArbiterStaking'))
    return ArbiterStakingFixture(network, deployer, nectar_token, bounty_registry, arbiter_staking)


@pytest.fixture
def erc20_relay(artifacts, eth_tester, web3):
    chain = Chain.HOMECHAIN
    fee_wallet = TestAccount(eth_tester)
    users = [TestAccount(eth_tester) for _ in range(2)]
    verifiers = [TestAccount(eth_tester) for _ in range(3)]
    verifier_manager = TestAccount(eth_tester)
    fee_manager = TestAccount(eth_tester)

    nectar_token = NectarToken(users + verifiers + [fee_wallet, verifier_manager, fee_manager], [])
    erc20_relay = ERC20Relay(nectar_token, fee_wallet, users, verifiers, verifier_manager, fee_manager)

    config = {
        'NectarToken': nectar_token.config(chain),
        'ERC20Relay': erc20_relay.config(chain),
    }

    network, deployer = deploy(config, chain, artifacts, eth_tester, web3)

    nectar_token.bind(deployer.contracts['NectarToken'])
    nectar_token.owner = network.address
    erc20_relay.bind(deployer.contracts['ERC20Relay'])
    erc20_relay.owner = network.address

    ERC20RelayFixture = namedtuple('ERC20RelayFixture',
                                   ('network', 'deployer', 'NectarToken', 'ERC20Relay'))
    return ERC20RelayFixture(network, deployer, nectar_token, erc20_relay)
