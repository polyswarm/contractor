import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'NectarToken'
PREDEPLOYED_ADDRESSES = {
    'mainnet': '0x0000000000000000000000000000000000000000',
    'rinkeby': '0x0000000000000000000000000000000000000000',
}


class NectarToken(Step):
    def run(self, network, deployer):
        if network.name in PREDEPLOYED_ADDRESSES:
            logger.warning('Using already deployed contract for network %s at %s', network.name,
                           PREDEPLOYED_ADDRESSES[network.name])

            deployer.at(CONTRACT_NAME, PREDEPLOYED_ADDRESSES[network.name])
        else:
            deployer.deploy(CONTRACT_NAME)
