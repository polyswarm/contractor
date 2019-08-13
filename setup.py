from setuptools import find_packages, setup


test_dependencies = [
        "coverage==4.5.1",
        "eth-tester[py-evm]==0.1.0b33",
        "pycodestyle==2.4.0",
        "pytest==4.0.0",
        "pytest-cov==2.6.0",
        "pytest-xdist==1.26.1",
    ]


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return [r for r in f.read().splitlines() if not r.startswith('git') and r not in test_dependencies]


setup(
    name='contractor',
    version='0.2.0',
    description='Utilities for Ethereum smart contract development and deployment',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/contracts',
    license='MIT',
    python_requires='>=3.5,<4',
    install_requires=parse_requirements() + ["py-solc @ git+http://github.com/polyswarm/py-solc.git@feature/0-5-3"],
    include_package_data=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'contractor=contractor.__main__:cli',
        ],
    },
)
