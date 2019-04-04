import hashlib
import logging

from contractor.network import Chain
from datetime import datetime
from sqlalchemy import create_engine, Boolean, Column, DateTime, Enum, ForeignKey, JSON, LargeBinary, Integer, String
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class Deployment(Base):
    """Database model for a deployment.
    """

    __tablename__ = 'deployments'
    id = Column(Integer, primary_key=True)
    community = Column(String)
    network = Column(String)
    network_id = Column(Integer)
    chain = Column(Enum(Chain))
    commit_hash = Column(String)
    tree_dirty = Column(Boolean)
    succeeded = Column(Boolean)
    timestamp = Column(DateTime)

    contracts = relationship('Contract', backref='deployment', cascade='all, delete-orphan')

    def __init__(self, community, network, network_id, chain, commit_hash=None, tree_dirty=None, succeeded=False,
                 timestamp=datetime.utcnow()):
        """Create a new deployment.

        :param community: Community that was deployed
        :param network: Network deployed to
        :param network_id: Network ID of network
        :param chain: Was this deployment on the homechain or sidechain
        :param commit_hash: Commit hash of the contractor version used in this deploy
        :param tree_dirty: Was the contractor source tree dirty (does source match commit hash)
        :param succeeded: Did the deployment succeed
        :param timestamp: Timestamp of deployment completion
        """
        self.community = community
        self.network = network
        self.network_id = network_id
        self.chain = chain
        self.commit_hash = commit_hash
        self.tree_dirty = tree_dirty
        self.succeeded = succeeded
        self.timestamp = timestamp

    def __repr__(self):
        """Return a human-readable representation of this deployment.

        :return: Human-readable representation of this deployment
        """
        return '<Deployment {0}, {1}, {2}, {3}, {4]>'.format(self.community, self.network, self.chain, self.timestamp,
                                                             'success' if self.succeeded else 'failed')


class Contract(Base):
    """Database model for a contract.
    """

    __tablename__ = 'contracts'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    deployed = Column(Boolean)
    address = Column(String)
    abi = Column(JSON(none_as_null=True))
    bytecode = Column(LargeBinary)
    config = Column(JSON(none_as_null=True))

    deployment_id = Column(Integer, ForeignKey('deployments.id'))

    def __init__(self, deployment, name, deployed, address, abi, bytecode, config):
        """Create a new contract.

        :param deployment: Deployment this contract is associated with
        :param name: Name of the contract
        :param deployed: Was this contract deployed
        :param address: Address of the deployed contract
        :param abi: JSON ABI of the deployed contract
        :param bytecode: Bytecode of the deployed contract
        :param config: Configuration used to deploy this contract
        """
        self.deployment_id = deployment.id
        self.name = name
        self.deployed = deployed
        self.address = address
        self.abi = abi
        self.bytecode = bytecode
        self.config = config

    def bytecode_hash(self):
        """Return a SHA-256 hash of the bytecode.

        :return: SHA-256 hash of the bytecode
        """
        return hashlib.sha256(self.bytecode)

    def __repr__(self):
        """Return a human-readable representation of this contract.

        :return: Human-readable representation of this contract
        """
        return '<Contract {0}, {1}, {2}, {3}>'.format(self.name, self.bytecode_hash(), self.address,
                                                      'deployed' if self.deployed else 'preexisting')


def connect(db_uri):
    """Connect to a database to record deployments.

    :param db_uri: Database URI to connect to
    :return: SQLAlchemy session for interacting with this database
    """
    engine = create_engine(db_uri, convert_unicode=True)
    session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    Base.query = session.query_property()
    Base.metadata.create_all(bind=engine)

    return session
