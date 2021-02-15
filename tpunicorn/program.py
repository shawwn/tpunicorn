import click
import tpunicorn
import json
import sys
import os
import time
import random
import math
from pprint import pprint as pp

import logging as pylogging
logging = tpunicorn.logger
logging.setLevel(pylogging.WARNING)

from tpunicorn._version import binary_names

# https://stackoverflow.com/questions/58666831/how-to-implement-version-using-python-click/58666832#58666832

@click.group()
@click.version_option(tpunicorn._version.__version__)
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def cli(ctx, **kws):
  ctx.obj = kws
  verbose = ctx.obj['verbose']
  if verbose:
    logging.setLevel(pylogging.DEBUG)
  logging.debug('%r', sys.argv)

def print_tpu_status_headers(color=True, project=None):
  message = tpunicorn.format(tpunicorn.format_headers(), project=project)
  if color:
    click.secho(message, bold=color)
  else:
    click.echo(message)

def print_tpu_status(tpu, format='text', color=True, project=None):
  if format == 'json':
    click.echo(json.dumps(tpu))
    return
  message = tpunicorn.format(tpu, project=project)
  if not color:
    click.echo(message)
  else:
    status = tpunicorn.format(tpu, '{status}', project=project)
    health = tpunicorn.format(tpu, '{health}', project=project)
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
    print_tpu_status_headers(color=color, project=project)
    for tpu in tpus:
      print_tpu_status(tpu, color=color, project=project)

@cli.command()
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
def top(zone, project):
  while True:
    click.clear()
    print_tpus_status(zone=zone, project=project)
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
  result = 0
  if command is not None:
    if dry_run:
      click.echo('Dry run; command skipped.')
      time.sleep(3.0)
    else:
      if callable(command):
        command(*args, **kwargs)
      else:
        result = os.system(command)
      time.sleep(delay_after)
  return result

@cli.command()
@click.argument('tpu', type=click.STRING, metavar="[TPU; default\"automatic\"]", autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('-v', '--version', type=click.STRING, metavar="[VERSION; default=\"1.15.3\"]", default="1.15.3",
              help="By default, the TPU is imaged with TF version 1.15.3, as we've found this to be the most stable over time."
                   " If your TPU is giving strange errors, try setting this to `nightly` and pray to moloch.")
@click.option('-a', '--accelerator-type', metavar="[ACCELERATOR_TYPE; default=\"v2-8\"]", type=click.STRING, default=None)
@click.option('--async', 'async_', is_flag=True)
@click.option('-d', '--description', metavar="DESCRIPTION", type=click.STRING, default=None)
@click.option('-n', '--network', metavar="[NETWORK; default=\"default\"]", type=click.STRING, default="default")
@click.option('-p/-np', '--preemptible/--non-preemptible', default=True)
@click.option('-r', '--range', metavar="[RANGE]", type=click.STRING, default=None)
@click.option('-p', '--project', metavar="[PROJECT]", type=click.STRING, default=None)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def create(tpu, zone, version, accelerator_type, async_, description, network, preemptible, range, project, yes, dry_run):
  index = tpunicorn.tpu.parse_tpu_index(tpu)
  if accelerator_type is None:
    accelerator_type = tpunicorn.tpu.parse_tpu_accelerator_type(tpu)
  # parse the TPU type and core count.
  tpu_type, cores = accelerator_type.rsplit("-", 1)
  tpu_type = tpu_type.lower()
  cores = int(cores)
  # give reasonable defaults for TFRC members
  if zone is None:
    zone = tpunicorn.tpu.parse_tpu_zone(tpu)
  if zone is None:
    if tpu_type == "v2" and cores == 8:
      zone = "us-central1-f"
    elif tpu_type == "v2" and cores > 8:
      zone = "us-central1-a"
    elif tpu_type == "v3":
      zone = "europe-west4-a"
    else:
      raise ValueError("Please specify --zone")
  if range is None and index >= 0:
    if cores == 8:
      range = "10.48.{i}.0/29".format(i=index)
    else:
      i=index + 2
      cidr=int(32 + 2 - math.log2(cores))
      range="10.{i}.0.0/{cidr}".format(i=i, cidr=cidr)
  if range.startswith("10.48.") and cores > 8:
    raise ValueError("The range {range!r} conflicts with the default 10.48.* range of v2-8's and v3-8's. I decided to raise an error rather than a warning, because we rely on this specific range for our own internal networking. If you're making a TPU pod, try a different index other than {index}. If you really, really wanted to use 10.48.* for you TPU pods, I'm very sorry; ping me on twitter (@theshawwn) and I'll change this.".format(range=range, index=index))
  try:
    index = int(tpu)
    # the TPU name is just an integer, so try to build a new name
    # automatically for convenience.
    zone_abbrev = tpunicorn.tpu.infer_zone_abbreviation(zone)
    tpu = "tpu-{accelerator_type}-{zone_abbrev}-{index}".format(
        accelerator_type=accelerator_type,
        zone_abbrev=zone_abbrev,
        index=index)
  except ValueError:
    pass
  if project is None:
    project = tpunicorn.tpu.get_default_project()
  create = tpunicorn.create_tpu_command(tpu, zone=zone, version=version, accelerator_type=accelerator_type, async_=async_, description=description, network=network, preemptible=preemptible, range=range, project=project)
  if not yes:
    print_step('Step 1: create TPU.', create)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: create TPU...', create, dry_run=dry_run)
  click.echo('TPU {} {} created.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))


@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--async', 'async_', is_flag=True)
def delete(tpu, zone, project, yes, dry_run, async_):
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  delete = tpunicorn.delete_tpu_command(tpu, zone=zone, project=project, async_=async_)
  create = tpunicorn.create_tpu_command(tpu, zone=zone, project=project, async_=async_)
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
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--async', 'async_', is_flag=True)
def stop(tpu, zone, project, yes, dry_run, async_):
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  stop = tpunicorn.stop_tpu_command(tpu, zone=zone, project=project, async_=async_)
  start = tpunicorn.start_tpu_command(tpu, zone=zone, project=project, async_=async_)
  if not yes:
    print_step('Step 1: stop TPU.', stop)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: stop TPU...', stop, dry_run=dry_run)
  click.echo('TPU {} {} stopped.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))
  print_step('You {} restart the TPU with:'.format('could then' if dry_run else 'can'),
    start)

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpunicorn.tpu.get_tpu_zones()))
@click.option('--project', type=click.STRING, default=None)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--async', 'async_', is_flag=True)
def start(tpu, zone, project, yes, dry_run, async_):
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  stop = tpunicorn.stop_tpu_command(tpu, zone=zone, project=project, async_=async_)
  start = tpunicorn.start_tpu_command(tpu, zone=zone, project=project, async_=async_)
  if not yes:
    print_step('Step 1: start TPU.', start)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: start TPU...', start, dry_run=dry_run)
  click.echo('TPU {} {} started.'.format(
    tpunicorn.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))
  print_step('You {} stop the TPU with:'.format('could then' if dry_run else 'can'),
    stop)

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
@click.option('--async', 'async_', is_flag=True)
def reimage(tpu, zone, project, version, yes, dry_run, async_):
  """Reimages the OS on a TPU."""
  tpu = tpunicorn.get_tpu(tpu=tpu, zone=zone, project=project)
  reimage = tpunicorn.reimage_tpu_command(tpu, zone=zone, project=project, version=version, async_=async_)
  def wait():
    wait_healthy(tpu, zone=zone, project=project)
  if not yes:
    print_step('Step 1: reimage TPU.', reimage)
    if not async_:
      print_step('Step 2: wait until TPU is HEALTHY.', wait)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: reimage TPU...', reimage, dry_run=dry_run)
  if not async_:
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
@click.option('--retry', type=int, help="if the TPU creation fails (due to capacity errors or otherwise), "
                                        "retry the creation command after this many seconds")
@click.option('--retry-randomness', type=float, default=1.0, help="multiply retry time by a float between 1 and retry_randomness")
def recreate(tpu, zone, project, version, yes, dry_run, preempted, command, retry, retry_randomness, **kws):
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
  while do_step('Step 2: create TPU...', create, dry_run=dry_run) != 0:
    if retry is None:
      click.echo('TPU {} failed to create (is the region out of capacity?)'.format(tpunicorn.tpu.parse_tpu_id(tpu)), err=True)
      break
    n = random.uniform(1, retry_randomness)
    click.echo('TPU {} failed to create; trying again in {} minutes...'.format(tpunicorn.tpu.parse_tpu_id(tpu),
                                                                               int((retry * n)//60)), err=True)
    time.sleep(retry * n)
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

