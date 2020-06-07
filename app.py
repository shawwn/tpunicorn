import click

@click.group()
@click.option('--debug/--no-debug')
def cli(debug):
  click.echo('Debug mode is %s' % ('on' if debug else 'off'))

@cli.command()
def hello():
  click.echo('Hello World!')

@cli.command()
def initdb():
  click.echo('Initialized the database')

@cli.command()
@click.confirmation_option(prompt='Are you sure you want to drop the db?')
def dropdb():
  click.echo('Dropped all tables!')

@cli.command()
@click.option('--username', required=True)
def greet(username):
  click.echo('Hello %s!' % username)

if __name__ == "__main__":
  cli(auto_envvar_prefix='TPUDIEPIE')
