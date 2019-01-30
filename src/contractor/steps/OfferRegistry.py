import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'OfferRegistry'


class OfferRegistry(Step):
    DEPENDENCIES = {'NectarToken'}

    def run(self, network, deployer):
        nectar_token_address = deployer.contracts['NectarToken'].address
        deployer.deploy(CONTRACT_NAME, nectar_token_address)
