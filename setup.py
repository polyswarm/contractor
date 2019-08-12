from setuptools import find_packages, setup


setup(
    name='contractor',
    version='0.2.0',
    description='Utilities for Ethereum smart contract development and deployment',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/contracts',
    license='MIT',
    python_requires='>=3.5,<4',
    install_requires=[
        "click==7.0",
        "ethereum==2.3.2",
        "eth-account==0.3.0",
        "hexbytes==0.1.0",
        "ipython==7.3.0",
        "requests==2.21.0",
        "psycopg2-binary==2.7.6.1",
        "python-consul==1.1.0",
        "PyYaml==5.1",
        "SQLAlchemy==1.3.0",
        "toposort==1.5",
        "tabulate==0.8.2",
        "trezor[ethereum,hidapi]==0.11.4",
        "web3==4.9.2"
    ],
    include_package_data=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'contractor=contractor.__main__:cli',
        ],
    },
)
