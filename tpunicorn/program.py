import click
import tpunicorn
import json
import sys
import os
import time
from pprint import pprint as pp

import logging as pylogging
logging = tpunicorn.logger
logging.setLevel(pylogging.WARNING)

from tpunicorn._version import binary_names

@click.group()
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def cli(ctx, **kws):
  ctx.obj = kws
  verbose = ctx.obj['verbose']
  if verbose:
    logging.setLevel(pylogging.DEBUG)
  logging.debug('%r', sys.argv)

def print_tpu_status_headers(color=True):
  message = tpunicorn.format(tpunicorn.format_headers())
  if color:
    click.secho(message, bold=color)
  else:
    click.echo(message)

def print_tpu_status(tpu, format='text', color=True):
  if format == 'json':
    click.echo(json.dumps(tpu))
    return
  message = tpunicorn.format(tpu)
  if not color:
    click.echo(message)
  else:
    status = tpunicorn.format(tpu, '{status}')
    health = tpunicorn.format(tpu, '{health}')
    if status == 'READY' and health == 'HEALTHY':
      click.secho(message, fg='green')
      return 'HEALTHY'
    elif status == 'PREEMPTED':
      click.secho(message, fg='red')
    else:
      click.secho(message, fg='yellow')

def print_tpus_status(zone=None, project=None, format='text', color=True):
  tpus = tpunicorn.get_tpus(zone=zone, project=project)
  if format == 'json':
    click.echo(json.dumps(tpus))
  else:
    assert format == 'text'
    print_tpu_status_headers(color=color)
    for tpu in tpus:
      print_tpu_status(tpu, color=color)

@cli.command()
def top():
  while True:
    click.clear()
    print_tpus_status()
    time.sleep(5.0)

@cli.command("list")
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.option('-c/-nc', '--color/--no-color', default=True)
@click.option('-t', '--tpu', type=click.STRING, help="List a specific TPU by id.", multiple=True)
@click.option('-s', '--silent', is_flag=True, help="If listing a specific TPU by ID, and there is no such TPU, don't throw an error.")
def list_tpus(zone, project, format, color, tpu, silent):
  """List TPUs."""
  tpus = tpu
  if len(tpus) <= 0:
    print_tpus_status(zone=zone, project=project, format=format, color=color)
  else:
    if format == 'text':
      print_tpu_status_headers()
    for tpu in tpus:
      tpu = tpunicorn.get_tpu(tpu, zone=zone, project=project, silent=silent)
      if tpu is not None:
        print_tpu_status(tpu, format=format, color=color)

def complete_tpu_id(ctx, args, incomplete, zone=None, project=None):
  tpus = tpunicorn.get_tpus(zone=zone, project=project)
  return [tpunicorn.tpu.parse_tpu_id(tpu) for tpu in tpus]

# @cli.command()
# @click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
# @click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
# @click.option('--project', type=click.STRING, default=None)
# def create(tpu, zone, project):
#   tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
#   create = tpunicorn.create_tpu_command(tpu)
#   click.echo(create)

def is_preempted(tpu, zone=None, project=None):
  tpu = tpunicorn.get_tpu(tpu, zone=zone, project=project)
  status = tpunicorn.format(tpu, '{status}')
  return status == 'PREEMPTED'

def check_healthy(tpu, zone=None, project=None, color=True, noisy=True):
  tpu = tpunicorn.get_tpu(tpu, zone=zone, project=project)
  if noisy:
    print_tpu_status(tpu, color=color)
  status = tpunicorn.format(tpu, '{status}')
  health = tpunicorn.format(tpu, '{health}')
  if status == 'READY' and health == 'HEALTHY':
    return True
  return False

def wait_healthy(tpu, zone=None, project=None, color=True):
  print_tpu_status_headers()
  while True:
    if check_healthy(tpu, zone=zone, project=project, color=color):
      return
    click.echo('TPU {} not yet healthy; waiting 30 seconds...'.format(tpunicorn.tpu.parse_tpu_id(tpu)))
    time.sleep(30.0)

def print_step(label=None, command=None, args=(), kwargs={}):
  click.echo('')
  if label is not None:
    click.secho(label, bold=True)
  if command is not None and not callable(command):
    click.echo('  $ ', nl=False)
    click.secho(command, fg='blue', bold=True)

def do_step(label=None, command=None, dry_run=False, delay_after=1.0, args=(), kwargs={}):
  print_step(label=label, command=command, args=args, kwargs=kwargs)
  if command is not None:
    if dry_run:
      click.echo('Dry run; command skipped.')
      time.sleep(3.0)
    else:
      if callable(command):
        command(*args, **kwargs)
      else:
        os.system(command)
      time.sleep(delay_after)

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def delete(tpu, zone, project, yes, dry_run):
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  delete = tpunicorn.delete_tpu_command(tpu, zone=zone, project=project)
  create = tpunicorn.create_tpu_command(tpu, zone=zone, project=project)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: delete TPU...', delete, dry_run=dry_run)
  click.echo('TPU {} {} deleted.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))
  print_step('You {} recreate the TPU with:'.format('could then' if dry_run else 'can'),
    create)

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('--version', type=click.STRING, metavar="<TF_VERSION>",
              help="By default, the TPU is reimaged with the same system software version."
                   " (This is handy as a quick way to reboot a TPU, freeing up all memory.)"
                   " You can set this to use a specific version, e.g. `nightly`.")
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def reimage(tpu, zone, project, version, yes, dry_run):
  """Reimages the OS on a TPU."""
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  reimage = tpunicorn.reimage_tpu_command(tpu, zone=zone, project=project, version=version)
  def wait():
    wait_healthy(tpu, zone=zone, project=project)
  if not yes:
    print_step('Step 1: reimage TPU.', reimage)
    print_step('Step 2: wait until TPU is HEALTHY.', wait)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: reimage TPU...', reimage, dry_run=dry_run)
  do_step('Step 2: wait for TPU to become HEALTHY...', wait, dry_run=dry_run)
  click.echo('TPU {} {} ready for training.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('--version', type=click.STRING, metavar="<TF_VERSION>",
              help="By default, the TPU is recreated with the same system software version."
                   " You can set this to use a specific version, e.g. `nightly`.")
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('-p', '--preempted', is_flag=True,
              help="Only recreate TPU if it has preempted."
                   """ (Specifically, if the tpu's STATE is "PREEMPTED",proceed; otherwise do nothing.)""")
@click.option('-c', '--command', type=click.STRING, multiple=True,
              help="After the TPU is HEALTHY, run this command."
              " (Useful for killing a training session after the TPU has been recreated.)")
def recreate(tpu, zone, project, version, yes, dry_run, preempted, command, **kws):
  """
  Recreates a TPU, optionally switching the system software to the specified TF_VERSION.
  """
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  click.echo('Current status of TPU {} as of {}:'.format(tpunicorn.tpu.parse_tpu_id(tpu), tpunicorn.tpu.get_timestamp()))
  print_tpu_status_headers()
  print_tpu_status(tpu)
  if preempted and not is_preempted(tpu, zone=zone, project=project):
    return
  click.echo('')
  delete = tpunicorn.delete_tpu_command(tpu, zone=zone, project=project)
  create = tpunicorn.create_tpu_command(tpu, zone=zone, project=project, version=version)
  def wait():
    wait_healthy(tpu, zone=zone, project=project)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
    print_step('Step 2: create TPU.', create)
    print_step('Step 3: wait until TPU is HEALTHY.', wait)
    if len(command) > 0:
      for i, cmd in enumerate(command):
        print_step('Step {}: run this command:'.format(i+4), cmd)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: delete TPU...', delete, dry_run=dry_run)
  do_step('Step 2: create TPU...', create, dry_run=dry_run)
  do_step('Step 3: wait for TPU to become HEALTHY...', wait, dry_run=dry_run)
  if len(command) > 0:
    for i, cmd in enumerate(command):
      do_step('Step {}: running command...'.format(i+4), cmd, dry_run=dry_run)
  click.echo('TPU {} {} ready for training.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('--dry-run', is_flag=True)
@click.option('-i', '--interval', type=click.INT, default=30, metavar='<seconds>',
              help='How often to check the TPU. (default: 30 seconds)')
@click.option('-c', '--command', type=click.STRING, multiple=True,
              help="After the TPU has been recreated and is HEALTHY, run this command."
                   " (Useful for killing a training session after the TPU has been recreated.)")
@click.pass_context
def babysit(ctx, tpu, zone, project, dry_run, interval, command):
  """Checks TPU every INTERVAL seconds. Recreates the TPU if (and only if) the tpu has preempted."""
  # cmd = cli.get_command(ctx, 'babysit')
  # ctx = click.Context(cmd, parent=ctx, ignore_unknown_options=True)
  ctx.forward(recreate, yes=True, preempted=True)
  while True:
    time.sleep(interval)
    try:
      ctx.forward(recreate, yes=True, preempted=True)
    except:
      import traceback
      traceback.print_exc()

completions = {
  'bash': {
    'script': 'eval "$(_{}_COMPLETE=source_bash {})"',
    'file': '~/.bash_profile' if sys.platform == 'darwin' else '~/.bashrc',
  },
  'zsh': {
    'script': 'eval "$(_{}_COMPLETE=source_zsh {})"',
    'file': '~/.zshrc',
  },
  'fish': {
    'script': 'eval (env _{}_COMPLETE=source_fish {})',
    'file': '~/.config/fish/completions/{}.fish',
  }
}

@cli.command()
@click.argument('shell', type=click.Choice(completions.keys()))
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def install_completion(shell, yes, dry_run):
  def install_completion(path, script, name):
    try:
      with click.open_file(path) as f:
        contents = f.read()
    except FileNotFoundError:
      contents = ''
    if script in contents:
      click.echo('Completion script {} already installed; skipping'.format(name))
      return
    if len(contents) > 0 and not contents.endswith('\n'):
      contents += '\n'
    contents += script + '\n'
    if dry_run:
      click.secho('Dry run; not writing. Would have appended to {} the following text:'.format(path), bold=True)
      click.echo(script)
    else:
      with click.open_file(path, 'w', atomic=True) as f:
        f.write(contents)
      click.secho('{} completion installed for `{}`'.format(shell, name), bold=True)
  scripts = [completions[shell]['script'].format(binary.upper().replace('-', ''), binary) for binary in binary_names]
  filename = os.path.expanduser(completions[shell]['file'])
  tasks = []
  for script, name in zip(scripts, binary_names):
    path = filename
    if '{}' in path:
      path = path.format(name)
    tasks.append(['Step {}: Append the completion script for {} to {}'.format(len(tasks)+1, name, path),
        install_completion, (path, script, name), {}])
  if not yes:
    for label, command, args, kwargs in tasks:
      print_step(label, command, args, kwargs)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  for label, command, args, kwargs in tasks:
    do_step(label + '..', command, args=args, kwargs=kwargs)

def main(*args, prog_name='tpunicorn', auto_envvar_prefix='TPUNICORN', **kws):
  cli.main(*args, prog_name=prog_name, auto_envvar_prefix=auto_envvar_prefix, **kws)

if __name__ == "__main__":
  main()

