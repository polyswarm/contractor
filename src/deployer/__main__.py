import click

from deployer.compiler import compile_directory


@click.group()
@click.option('--external', type=str)
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@click.option('--external', type=str)
@click.argument('srcdir', nargs=1)
@click.argument('outdir', nargs=1)
@click.pass_context
def compile(ctx, external, srcdir, outdir):
    compile_directory(srcdir, outdir, external)


if __name__ == '__main__':
    cli(obj={})
