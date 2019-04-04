import logging

from contractor.steps import Step

logger = logging.getLogger(__name__)

CONTRACT_NAME = 'ArbiterStaking'


class ArbiterStaking(Step):
    """Deployment steps for the ArbiterStaking contract.
    """

    DEPENDENCIES = {'NectarToken'}
    """ArbiterStaking depends on NectarToken"""

    def run(self, network, deployer):
        """Run the deployment.

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        nectar_token_address = deployer.contracts['NectarToken'].address

        contract_config = network.contract_config.get(CONTRACT_NAME, {})
        stake_duration = contract_config.get('stake_duration', 100)

        deployer.deploy(CONTRACT_NAME, nectar_token_address, stake_duration)
