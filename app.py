import click
import tpudiepie
import json
import sys
import os
from pprint import pprint as pp

@click.group()
def cli():
  pass

@cli.command()
@click.option('--zone', default=None)
@click.option('--format', default='text')
@click.option('-c/-nc', '--color/--no-color', default=True)
def list(zone, format, color):
  tpus = tpudiepie.get_tpus(zone=zone)
  if format == 'json':
    click.echo(json.dumps(tpus))
  else:
    assert format == 'text'
    message = tpudiepie.format(tpudiepie.format_headers())
    click.secho(message, bold=color)
    for tpu in tpus:
      message = tpudiepie.format(tpu)
      if not color:
        click.echo(message)
      else:
        status = tpudiepie.format(tpu, '{status}')
        health = tpudiepie.format(tpu, '{health}')
        if status == 'READY' and health == 'HEALTHY':
          click.secho(message, fg='green')
        elif status == 'PREEMPTED':
            click.secho(message, fg='red')
        else:
          click.secho(message, fg='yellow')

@cli.command()
@click.argument('tpu')
@click.option('--zone', default=None)
@click.confirmation_option('-y', '--yes', prompt='Are you sure you want to delete this tpu?')
def delete(tpu, zone):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  #click.echo("Deleting TPU {}".format(tpu['name']))
  click.echo(tpudiepie.create_tpu_command(tpu))

if __name__ == "__main__":
  cli(auto_envvar_prefix='TPUDIEPIE')

