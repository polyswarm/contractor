import logging
import os

from base64 import b64encode
from consul import Consul
from consul.base import Timeout
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ConsulClient(object):
    def __init__(self, uri, token):
        u = urlparse(uri)
        self.client = Consul(host=u.hostname, port=u.port, scheme=u.scheme, token=token)

    def __fetch_from_consul_or_wait(self, key, recurse=False, index=0):
        logger.info('Fetching key: %s', key)
        while True:
            try:
                index, data = self.client.kv.get(key, recurse=recurse, index=index, wait='2m')
                if data is not None:
                    return data
            except Timeout:
                logger.info('Consul key %s not available, retrying...', key)
                continue

    def pull_config(self, community, out_dir):
        # TODO: Should `chain/foo` really be `community/foo`?
        key = 'chain/{}/'.format(community)
        values = self.__fetch_from_consul_or_wait(key, recurse=True)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        for value in values:
            filename = os.path.join(out_dir, value['Key'].split('/')[-1] + '.json')

            logger.info('Writing %s', filename)
            with open(filename, 'w') as f:
                f.write(str(value['Value']))

    def push_config(self, community, in_dir):
        # TODO: Should `chain/foo` really be `community/foo`?
        base_key = 'chain/{}/'.format(community)

        ops = []
        for root, dirs, files in os.walk(in_dir):
            for file in files:
                filename = os.path.join(root, file)
                logger.info('Adding contents of %s to transaction', filename)

                with open(filename, 'rb') as f:
                    value = b64encode(f.read()).decode('utf-8')
                    ops.append((base_key + os.path.splitext(file)[0], value))

        # Transform ops into a transaction that consul expects
        tx = [{
            'KV': {
                'Verb': 'set',
                'Key': key,
                'Value': value,
            },
        } for key, value in ops]

        logger.info('Pushing transaction to consul')
        self.client.txn.put(tx)

