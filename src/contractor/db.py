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
        self.community = community
        self.network = network
        self.network_id = network_id
        self.chain = chain
        self.commit_hash = commit_hash
        self.tree_dirty = tree_dirty
        self.succeeded = succeeded
        self.timestamp = timestamp

    def __repr__(self):
        return '<Deployment {0}, {1}, {2}, {3}, {4]>'.format(self.community, self.network, self.chain, self.timestamp,
                                                             'success' if self.succeeded else 'failed')


class Contract(Base):
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
        self.deployment_id = deployment.id
        self.name = name
        self.deployed = deployed
        self.address = address
        self.abi = abi
        self.bytecode = bytecode
        self.config = config

    def bytecode_hash(self):
        return hashlib.sha256(self.bytecode)

    def __repr__(self):
        return '<Contract {0}, {1}, {2}, {3}>'.format(self.name, self.bytecode_hash(), self.address,
                                                      'deployed' if self.deployed else 'preexisting')


def connect(db_uri):
    engine = create_engine(db_uri, convert_unicode=True)
    session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    Base.query = session.query_property()
    Base.metadata.create_all(bind=engine)

    return session
