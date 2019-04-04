import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'OfferRegistry'


class OfferRegistry(Step):
    """Deployment steps for the OfferRegistry contract.
    """

    DEPENDENCIES = {'NectarToken'}
    """OfferRegistry depends on NectarToken"""

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address
        deployer.deploy(CONTRACT_NAME, nectar_token_address)
