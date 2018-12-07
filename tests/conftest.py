import os
import shutil
import tempfile

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from contractor.compiler import DEFAULT_SOLC_VERSION
from contractor.compiler import compile_directory
from contractor.deployer import Deployer


@pytest.fixture(scope='session')
def artifacts():
    basedir = os.path.join(os.path.dirname(__file__), '..')
    srcdir = os.path.join('contracts')
    extdir = os.path.join('external')
    outdir = tempfile.mkdtemp()

    compile_directory(DEFAULT_SOLC_VERSION, srcdir, outdir, extdir)

    yield outdir

    shutil.rmtree(outdir)


@pytest.fixture
def web3():
    tester = EthereumTester(PyEVMBackend())
    provider = EthereumTesterProvider(tester)
    w3 = Web3(provider)

    return w3


@pytest.fixture
def contracts(web3, artifacts):
    print(artifacts)
