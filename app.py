import click
import tpudiepie

@click.group()
def cli():
  pass

@cli.command()
@click.option('--zone', default="europe-west4-a")
@click.option('--color/--no-color', default=True)
def list(zone, color):
  message = tpudiepie.format(tpudiepie.format_headers())
  click.secho(message, bold=color)
  for tpu in tpudiepie.get_tpus(zone=zone):
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

if __name__ == "__main__":
  cli(auto_envvar_prefix='TPUDIEPIE')

