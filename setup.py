from setuptools import setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return f.read().splitlines()


setup(
    name='contracts',
    version='0.1.0',
    description='Utilities for Ethereum smart contract development and deployment',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/contracts',
    license='MIT',
    python_requires='>=3.5,<4',
    install_requires=parse_requirements(),
    include_package_data=True,
    packages=['deployer'],
    package_dir={
        'deployer': 'src/deployer',
    },
    entry_points={
        'console_scripts': [
            'deployer=deployer.__main__:main',
        ],
    },
)
