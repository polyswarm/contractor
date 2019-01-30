import os

import click

from contractor.compiler import configure_compiler
from contractor.util import call_with_output


def slither_analyze_directory(solc_version, src_dir, ext_dir=None, excludes=[]):
    solc_path = configure_compiler(solc_version)

    cmd = ['slither', '--solc', solc_path]
    for exclude in excludes:
        if exclude in ('informational', 'low', 'medium', 'high'):
            cmd.append('--exclude-' + exclude)
        else:
            cmd.extend(('--exclude', exclude))

    remappings = []
    if ext_dir:
        for ext in os.listdir(ext_dir):
            remappings.append(ext + '=' + os.path.join(ext_dir, ext))

    if remappings:
        # Need to hack slither a bit to pass in remappings to solc, use a dummy argument
        cmd.extend(('--solc-args', '--ignore-missing ' + ' '.join(remappings)))

    cmd.append(src_dir)
    try:
        return call_with_output(cmd)
    except FileNotFoundError:
        click.echo('slither executable not found, is it installed and in PATH?')
        return 1
