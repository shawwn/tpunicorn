import click
import tpudiepie
import json
import sys
import os
import time
from pprint import pprint as pp

import logging as pylogging
logging = tpudiepie.logger
logging.setLevel(pylogging.WARNING)

from tpudiepie._version import binary_names

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
  message = tpudiepie.format(tpudiepie.format_headers())
  if color:
    click.secho(message, bold=color)
  else:
    click.echo(message)

def print_tpu_status(tpu, color=True):
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
    return status, health

def print_tpus_status(zone=None, format='text', color=True):
  tpus = tpudiepie.get_tpus(zone=zone)
  if format == 'json':
    click.echo(json.dumps(tpus))
  else:
    assert format == 'text'
    print_tpu_status_headers(color=color)
    for tpu in tpus:
      print_tpu_status(tpu, color=color)

def watch_status():
  while True:
    click.clear()
    print_tpus_status()
    time.sleep(5.0)

@cli.command()
def top():
  watch_status()

@cli.command()
def tail():
  watch_status()

@cli.command()
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.option('-c/-nc', '--color/--no-color', default=True)
def status(zone, format, color):
  print_tpus_status(zone=zone, format=format, color=color)

def complete_tpu_id(ctx, args, incomplete, zone=None):
  tpus = tpudiepie.get_tpus(zone=zone)
  return [tpudiepie.tpu.parse_tpu_id(tpu) for tpu in tpus]

# @cli.command()
# @click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
# @click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
# def create(tpu, zone):
#   tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
#   create = tpudiepie.create_tpu_command(tpu)
#   click.echo(create)

def check_healthy(tpu, zone=None, color=True, noisy=False):
  tpu = tpudiepie.get_tpu(tpu, zone=zone)
  if noisy:
    print_tpu_status_headers()
    print_tpu_status(tpu, color=color)
  status = tpudiepie.format(tpu, '{status}')
  health = tpudiepie.format(tpu, '{health}')
  if status == 'READY' and health == 'HEALTHY':
    return True, tpu
  return False, tpu

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('-c/-nc', '--color/--no-color', default=True)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--delete-after-minutes', type=click.FLOAT, default=15.0)
@click.pass_context
def wait_healthy(ctx, tpu, zone, color, yes, dry_run, delete_after_minutes, **kws):
  ok, tpu = check_healthy(tpu, color=color, noisy=True)
  if ok:
    return True
  started = time.time()
  while True:
    elapsed = time.time() - started
    remain = 30.0
    if delete_after_minutes is not None and delete_after_minutes > 0.0:
      remain = delete_after_minutes*60 - elapsed
      remain_min = int(remain // 60)
      remain_sec = int(remain % 60)
      click.echo('TPU {} not yet healthy; {:02d}m{:02d}s until I delete and recreate it...'.format(tpudiepie.tpu.parse_tpu_id(tpu), remain_min, remain_sec))
    else:
      click.echo('TPU {} not yet healthy...'.format(tpudiepie.tpu.parse_tpu_id(tpu)))
    time.sleep(min(remain, 30.0) + 1.0)
    elapsed = time.time() - started
    if delete_after_minutes is not None and elapsed/60 >= delete_after_minutes:
      do_step("It's been {} minutes and the TPU still isn't healthy; recreating it.".format(delete_after_minutes))
      return ctx.forward(recreate, yes=True, **kws)
    try:
      ok, _ = check_healthy(tpu, color=color, noisy=True)
      if ok:
        return True
    except tpudiepie.tpu.TPUNotFoundError:
      click.secho('TPU {} not found. (Was it deleted by someone else?) Recreating it...'.format(tpudiepie.tpu.parse_tpu_id(tpu)), bold=True)
      assert isinstance(tpu, dict)
      create = tpudiepie.create_tpu_command(tpu, zone=zone)
      do_step('Creating TPU...', create)
      started = time.time() # reset deletion countdown
      continue
  raise Exception('Should not get here')

def print_shell(command):
  click.echo('  $ ', nl=False)
  click.secho(command, fg='blue', bold=True)

def print_step(label=None, command=None, args=(), kwargs={}):
  click.echo('')
  if label is not None:
    click.secho(label, bold=True)
  if command is not None and not callable(command):
    print_shell(command)

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
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--version', type=click.STRING)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.pass_context
def delete(ctx, tpu, zone, version, yes, dry_run, **kws):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  delete = tpudiepie.delete_tpu_command(tpu, zone=zone)
  create = tpudiepie.create_tpu_command(tpu, zone=zone, version=version)
  def wait():
    ctx.forward(wait_healthy, tpu=tpu, **kws)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
    click.echo('')
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: delete TPU...', delete, dry_run=dry_run)
  click.echo('TPU {} {} deleted.'.format(
    tpudiepie.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))
  print_step('You {} recreate the TPU with:'.format('could then' if dry_run else 'can'),
    create)

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--version', type=click.STRING)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.pass_context
def reimage(ctx, tpu, zone, version, yes, dry_run, **kws):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  reimage = tpudiepie.reimage_tpu_command(tpu, version=version)
  def wait():
    ctx.forward(wait_healthy, tpu=tpu, **kws)
  if not yes:
    print_step('Step 1: reimage TPU.', reimage)
    print_step('Step 2: wait until TPU is HEALTHY.', wait)
    click.echo('')
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: reimage TPU...', reimage, dry_run=dry_run)
  do_step('Step 2: wait for TPU to become HEALTHY...', wait, dry_run=dry_run)
  click.echo('TPU {} {} ready for training.'.format(
    tpudiepie.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--version', type=click.STRING)
@click.option('-c/-nc', '--color/--no-color', default=True)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--ensure', is_flag=True, help="If TPU is healthy, don't do anything.")
@click.option('--delete-after-minutes', type=click.FLOAT, default=15.0)
@click.pass_context
def recreate(ctx, tpu, zone, version, color, yes, dry_run, ensure, delete_after_minutes, **kws):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  print_tpu_status_headers(color=color)
  status, health = print_tpu_status(tpu, color=color)
  if ensure and status == 'READY' and health == 'HEALTHY':
    return 0
  if ensure and status in ['CREATING', 'STARTING', 'RESTARTING', 'REIMAGING', 'DELETING', 'STOPPING']:
    return 1
  else:
    if health not in ['UNHEALTHY_TENSORFLOW']:
      delete = tpudiepie.delete_tpu_command(tpu, zone=zone)
    else:
      delete = None
    create = tpudiepie.create_tpu_command(tpu, zone=zone, version=version)
  def wait():
    ctx.forward(wait_healthy, tpu=tpu, **kws)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
    print_step('Step 2: create TPU.', create)
    print_step('Step 3: wait until TPU is HEALTHY.', wait)
    click.echo('')
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: delete TPU...', delete, dry_run=dry_run)
  do_step('Step 2: create TPU...', create, dry_run=dry_run)
  do_step('Step 3: wait for TPU to become HEALTHY...', wait, dry_run=dry_run)
  click.echo('TPU {} {} ready for training.'.format(
    tpudiepie.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--version', type=click.STRING)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--forever', is_flag=True)
@click.pass_context
def ensure(ctx, tpu, zone, version, yes, dry_run, forever, **kws):
  while True:
    ctx.forward(recreate, ensure=True, **kws)
    if not forever:
      break
    time.sleep(30.0)

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
    click.echo('')
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  for label, command, args, kwargs in tasks:
    do_step(label + '..', command, args=args, kwargs=kwargs)

def main(*args, prog_name='tpudiepie', auto_envvar_prefix='TPUDIEPIE', **kws):
  cli.main(*args, prog_name=prog_name, auto_envvar_prefix=auto_envvar_prefix, **kws)

if __name__ == "__main__":
  main()

