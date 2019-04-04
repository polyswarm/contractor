import click

from contractor.util import call_with_output


def solium_analyze_directory(src_dir):
    """Analyze contract source code using `solium (ethlint) <https://github.com/duaraghav8/Ethlint>`_.

    :param solc_version: Version of Solidity compiler to use
    :return: 0 on success non-zero on failure
    """
    cmd = ['solium', '-d', src_dir]
    try:
        return call_with_output(cmd)
    except FileNotFoundError:
        click.echo('solium executable not found, is it installed and in PATH?')
        return 1
