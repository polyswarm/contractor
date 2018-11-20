import click

from deployer.compiler import compiler_json_from_directory


@click.group()
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@click.argument('dir', nargs=1)
@click.pass_context
def compile(ctx, dir):
    compiler_json_from_directory(dir)


if __name__ == '__main__':
    cli(obj={})
