import click
import logging
import sys

from contractor import db, steps
from contractor.compiler import compile_directory
from contractor.config import Config, Chain
from contractor.consul import ConsulClient
from contractor.deployer import Deployer


@click.group()
@click.pass_context
def cli(ctx):
    logging.basicConfig(level=logging.INFO)
    ctx.ensure_object(dict)


@cli.command()
@click.option('-i', '--srcdir', type=click.Path(exists=True, file_okay=False), default='contracts',
              help='Directory containing the solidity source to compile')
@click.option('-e', '--external', type=click.Path(exists=True, file_okay=False), default='external',
              help='Directory containing any external libraries used')
@click.option('-o', '--outdir', type=click.Path(file_okay=False), default='build',
              help='Directory to store the compiled json output for later deployment')
@click.pass_context
def compile(ctx, srcdir, external, outdir):
    is_dirty = compile_directory(srcdir, outdir, external)

    # If there are no contract changes, exit with failure to signal to not attempt a redeploy
    if not is_dirty:
        logging.info('No contract differences detected, exiting with failure')
        sys.exit(2)


@cli.command()
@click.option('--config', envvar='CONFIG', type=click.File('r'), required=True,
              help='Path to yaml config file defining networks and users')
@click.option('--community', envvar='COMMUNITY', required=True,
              help='What community we are deploying for')
@click.option('--network', required=True,
              help='What network to deploy to')
@click.option('--keyfile', envvar='KEYFILE', type=click.File('r'), required=True,
              help='Path to private key json file used to deploy')
@click.option('--password', envvar='PASSWORD', prompt=True, hide_input=True,
              help='Password used to decrypt private key')
@click.option('--chain', type=click.Choice(('home', 'side')), required=True,
              help='Is this deployment on the homechain or sidechain?')
@click.option('--db-uri', envvar='DB_URI',
              help='URI for the deployment database')
@click.option('--git/--no-git', default=True,
              help='Record git commit hash and tree status, assumes artifactdir is in repository')
@click.option('-i', '--artifactdir', type=click.Path(exists=True, file_okay=False), default='build',
              help='Directory containing the compiled artifacts to deploy')
@click.option('-o', '--output', type=click.Path(dir_okay=False, writable=True), required=False,
              help='File to output deployment results json to')
@click.pass_context
def deploy(ctx, config, community, network, keyfile, password, chain, db_uri, git, artifactdir, output):
    config = Config.from_yaml(config, Chain.from_str(chain))

    network = config.networks[network]
    network.connect(keyfile, password)

    session = None
    if db_uri is not None:
        session = db.connect(db_uri)

    deployer = Deployer(community, network, artifactdir, record_git_status=git, session=session)

    steps.run(network, deployer)

    # Default to homechain.json/sidechain.json
    if not output:
        output = chain + 'chain.json'

    with open(output, 'w') as f:
        deployer.dump_results(f)


@cli.group()
@click.pass_context
def consul(ctx):
    pass


@consul.command()
@click.option('-u', '--consul-uri', envvar='CONSUL_URI', required=True,
              help='URI for consul')
@click.option('-t', '--consul-token', envvar='CONSUL_TOKEN', default='',
              help='Token for consul access')
@click.option('-c', '--community', envvar='COMMUNITY', required=True,
              help='Community to access')
@click.option('--wait/--no-wait', default=False,
              help='Wait for key to become available')
@click.option('-o', '--outdir', type=click.Path(file_okay=False), default='consul',
              help='Directory to store the pulled consul keys to')
@click.pass_context
def pull(ctx, consul_uri, consul_token, community, wait, outdir):
    c = ConsulClient(consul_uri, consul_token)
    c.pull_config(community, outdir, wait=wait)


@consul.command()
@click.option('-u', '--consul-uri', envvar='CONSUL_URI', required=True,
              help='URI for consul')
@click.option('-t', '--consul-token', envvar='CONSUL_TOKEN', default='',
              help='Token for consul access')
@click.option('-c', '--community', envvar='COMMUNITY', required=True,
              help='Community to access')
@click.option('-i', '--indir', type=click.Path(exists=True, file_okay=False), default='consul',
              help='Directory containing the contents of consul keys to push')
@click.pass_context
def push(ctx, consul_uri, consul_token, community, indir):
    c = ConsulClient(consul_uri, consul_token)
    c.push_config(community, indir)


if __name__ == '__main__':
    cli(obj={})
