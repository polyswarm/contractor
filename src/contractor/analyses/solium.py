import click

from contractor.util import call_with_output


def solium_analyze_directory(src_dir):
    cmd = ['solium', '-d', src_dir]
    try:
        return call_with_output(cmd)
    except FileNotFoundError:
        click.echo('solium executable not found, is it installed and in PATH?')
        return 1
