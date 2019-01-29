from setuptools import find_packages, setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return [r for r in f.read().splitlines() if not r.startswith('git')]


setup(
    name='contractor',
    version='0.2.0',
    description='Utilities for Ethereum smart contract development and deployment',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/contracts',
    license='MIT',
    python_requires='>=3.5,<4',
    install_requires=parse_requirements(),
    include_package_data=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'contractor=contractor.__main__:cli',
        ],
    },
)
