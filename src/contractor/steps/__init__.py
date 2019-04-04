import logging
import pkgutil
import sys

from toposort import toposort_flatten

logger = logging.getLogger(__name__)
REGISTRY = {}


def register_class(cls):
    """Register a class' existence in the registry.

    :param cls: Class to register
    :return: None
    """
    REGISTRY[cls.__name__] = cls


class __MetaRegistry(type):
    """Metaclass to facilitate registration of subclasses in the registry.
    """

    def __new__(typ, name, bases, class_dict):
        """Register a class' existence in the registry upon import.

        :param name: Name of the class
        :param bases: Base classes
        :param class_dict: Class dictionary
        :return: New class
        """
        cls = type.__new__(typ, name, bases, class_dict)
        if bases[0] != object:
            register_class(cls)
        return cls


class Step(object, metaclass=__MetaRegistry):
    """Deployment step for a contract
    """

    DEPENDENCIES = set()
    """Dependencies of this step which must be performed first"""

    def run(self, network, deployer):
        """Run this deployment step

        :param network: Network being deployed to
        :param deployer: Deployer for deploying and transacting with contracts
        :return: None
        """
        pass

    def validate(self, network):
        """Ensures prerequisites for step and configuration are correct before proceeding.

        :param network: Network being deployed to
        :return: True if valid, else False
        """
        return True


def run(network, deployer, to_deploy=None):
    """Run all deployment steps in order.

    :param network: Network being deployed to
    :param deployer: Deployer for deploying and transacting with contracts
    :param to_deploy: List of what steps to perform, by default all steps will be run
    :return: None
    """
    # Load all our submodules so they get registered
    for importer, modname, ispkg in pkgutil.iter_modules(sys.modules[__name__].__path__):
        importer.find_module(modname).load_module(modname)

    contracts = REGISTRY
    if to_deploy is not None:
        contracts = {k: v for k, v in REGISTRY.items() if k in to_deploy}

    depgraph = {k: v.DEPENDENCIES for k, v in contracts.items()}
    ordered_steps = [(k, contracts[k]()) for k in toposort_flatten(depgraph)]

    logger.info('Deployment order: %s', ', '.join([x[0] for x in ordered_steps]))

    for name, step in ordered_steps:
        if not step.validate(network):
            raise ValueError('Preconditions not met for contract {}, check config'.format(name))

    for name, step in ordered_steps:
        logger.info('Running deployment for %s', name)
        step.run(network, deployer)
