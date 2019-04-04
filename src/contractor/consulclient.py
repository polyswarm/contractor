import json
import logging
import os

from consul import Consul
from consul.base import Timeout
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

INITIAL_WAIT = '5s'
LONG_WAIT = '2m'


class ConsulClient(object):
    """Client for interacting with Consul.
    """

    def __init__(self, uri, token):
        """Create a new ConsulClient for interacting with a given URI with an access token.

        :param uri: URI of Consul agent
        :param token: Access token to use
        """
        u = urlparse(uri)
        self.client = Consul(host=u.hostname, port=u.port, scheme=u.scheme, token=token)

    def __fetch_from_consul_or_wait(self, key, recurse=False, index=0):
        """Fetch a key from Consul once it becomes available (blocking).

        :param key: Key to fetch
        :param recurse: Is this a recursive fetch
        :param index: Index of operation
        :return: Key value once available
        """
        logger.info('Fetching key: %s', key)
        while True:
            try:
                index, data = self.client.kv.get(key, recurse=recurse, index=index, wait=LONG_WAIT)
                if data is not None:
                    return data
            except Timeout:
                logger.info('Consul key %s not available, retrying...', key)
                continue

    def pull_config(self, community, out_dir, wait=True):
        """Pull a set of configuration files from Consul into a directory.

        :param community: Community to access
        :param out_dir: Directory to place pulled configuration
        :param wait: Should we wait if key is not yet available
        :return: None
        """
        # TODO: Should `chain/foo` really be `community/foo`?
        key = 'chain/{}/'.format(community)
        index, values = self.client.kv.get(key, recurse=True, index=0, wait=INITIAL_WAIT)
        if values is None and wait:
            logger.info('Waiting for consul key %s to become available', key)
            values = self.__fetch_from_consul_or_wait(key, recurse=True, index=index)

        if values is None:
            logger.info('Consul key %s is not available, continuing', key)
            return

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        for value in values:
            filename = os.path.join(out_dir, value['Key'].split('/')[-1] + '.json')

            logger.info('Writing %s', filename)
            with open(filename, 'w') as f:
                f.write(value['Value'].decode('utf-8'))

    def push_config(self, community, in_dir):
        """Push a set of configuration files from a directory into Consul.

        :param community: Community to access
        :param in_dir: Directory containing new configuration
        :return: None
        """
        # TODO: Should `chain/foo` really be `community/foo`?
        base_key = 'chain/{}/'.format(community)

        # Write the contract keys first outside of transaction to avoid consul size limits
        written = set()
        for root, dirs, files in os.walk(in_dir):
            for file in files:
                key = base_key + os.path.splitext(file)[0]
                filename = os.path.join(root, file)

                try:
                    with open(filename, 'r') as f:
                        value = json.load(f)
                except ValueError as e:
                    logger.error('Error parsing %s as json, skipping: %s', filename, e)
                    continue

                # TODO: Restore transactional update, causing breakage in infrastructure
                logger.info('Pushing contents of %s to consul', filename)
                self.client.kv.put(key, json.dumps(value))
                written.add(filename)
