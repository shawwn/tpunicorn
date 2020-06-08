import click
import tpudiepie
import json
import sys
import os
from pprint import pprint as pp

import logging as pylogging
logging = tpudiepie.logger
logging.setLevel(pylogging.WARNING)

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
      return 'HEALTHY'
    elif status == 'PREEMPTED':
      click.secho(message, fg='red')
    else:
      click.secho(message, fg='yellow')

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
def list(zone, format, color):
  print_tpus_status(zone=zone, format=format, color=color)

list_tpus = list

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

def check_healthy(tpu, zone=None, color=True):
  tpu = tpudiepie.get_tpu(tpu, zone=zone)
  print_tpu_status(tpu, color=color)
  status = tpudiepie.format(tpu, '{status}')
  health = tpudiepie.format(tpu, '{health}')
  if status == 'READY' and health == 'HEALTHY':
    return True
  return False

def wait_healthy(tpu, zone=None, color=True):
  while True:
    if check_healthy(tpu, color=color):
      return
    click.echo('TPU {} not yet healthy; waiting 30 seconds...'.format(tpudiepie.tpu.parse_tpu_id(tpu)))
    time.sleep(30.0)

def print_step(label=None, command=None):
  click.echo('')
  if label is not None:
    click.secho(label, bold=True)
  if command is not None and not callable(command):
    click.echo('  $ ', nl=False)
    click.secho(command, fg='blue', bold=True)

def do_step(label=None, command=None, dry_run=False, delay_after=1.0):
  print_step(label=label, command=command)
  if command is not None:
    if dry_run:
      click.echo('Dry run; command skipped.')
      time.sleep(3.0)
    else:
      if callable(command):
        command()
      else:
        os.system(command)
      time.sleep(delay_after)

@cli.command()
@click.argument('tpu', type=click.STRING, autocompletion=complete_tpu_id)
@click.option('--zone', type=click.Choice(tpudiepie.tpu.get_tpu_zones()))
@click.option('--version', type=click.STRING)
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def delete(tpu, zone, version, yes, dry_run):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  delete = tpudiepie.delete_tpu_command(tpu, zone=zone)
  create = tpudiepie.create_tpu_command(tpu, zone=zone, version=version)
  def wait():
    wait_healthy(tpu, zone=zone)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
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
def reimage(tpu, zone, version, yes, dry_run):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  reimage = tpudiepie.reimage_tpu_command(tpu, version=version)
  def wait():
    wait_healthy(tpu, zone=zone)
  if not yes:
    print_step('Step 1: reimage TPU.', reimage)
    print_step('Step 2: wait until TPU is HEALTHY.', wait)
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
@click.option('-y', '--yes', is_flag=True)
@click.option('--dry-run', is_flag=True)
def recreate(tpu, zone, version, yes, dry_run):
  tpu = tpudiepie.get_tpu(tpu=tpu, zone=zone)
  click.echo('Current status of TPU:')
  print_tpu_status_headers()
  print_tpu_status(tpu)
  click.echo('')
  delete = tpudiepie.delete_tpu_command(tpu, zone=zone)
  create = tpudiepie.create_tpu_command(tpu, zone=zone, version=version)
  def wait():
    wait_healthy(tpu, zone=zone)
  if not yes:
    print_step('Step 1: delete TPU.', delete)
    print_step('Step 2: create TPU.', create)
    print_step('Step 3: wait until TPU is HEALTHY.', wait)
    if not click.confirm('Proceed? {}'.format('(dry run)' if dry_run else '')):
      return
  do_step('Step 1: delete TPU...', delete, dry_run=dry_run)
  do_step('Step 2: create TPU...', create, dry_run=dry_run)
  do_step('Step 3: wait for TPU to become HEALTHY...', wait, dry_run=dry_run)
  click.echo('TPU {} {} ready for training.'.format(
    tpudiepie.tpu.parse_tpu_id(tpu),
    'would be' if dry_run else 'is'))

# @cli.command()
# @click.argument('cmd', nargs=-1)
# def run(cmd):
#   #pp(sys.argv)
#   #pp(cmd)
#   #os.execvp(cmd[0], cmd[1:])
#   # os.setpgid(0, 0)
#   # newpid = os.fork()
#   # if newpid == 0:
#   os.execvp(cmd[0], cmd)

import signal
import subprocess


try:
    _ALL_SIGNALS = signal.valid_signals()
except AttributeError:
    # Only exists on Python 3.8+
    _ALL_SIGNALS = range(1, signal.NSIG)


def block_all_signals():
    """Block asynchronous delivery of all signals to this process."""
    #breakpoint()
    signal.pthread_sigmask(signal.SIG_BLOCK, _ALL_SIGNALS)


def _forward_signal(signum, target_pid, process_name):
    logging.debug("Forwarding signal %d to process %s.", signum, process_name)
    try:
        os.kill(target_pid, signum)
    except OSError as e:
        logging.debug(
            "Could not forward signal %d to process %s: %s", signum, process_name, e
        )

def wait_for_child_and_forward_signals(child_pid, process_name):
    """Wait for a child to terminate and in the meantime forward all signals
    that the current process receives to this child.
    @return a tuple of exit code and resource usage of the child as given by os.waitpid
    """
    block_all_signals()

    while True:
        logging.debug("Waiting for signals")
        signum = signal.sigwait(_ALL_SIGNALS)
        logging.debug("Received signal %r for PID %r", signum, child_pid)
        if signum == signal.SIGCHLD:
          logging.debug("os.wait4(-1, os.WNOHANG)")
          pid, exitcode, ru_child = os.wait4(-1, os.WNOHANG)
          logging.debug("pid=%r, exitcode=%r, ru_child=%r = os.wait4(-1, os.WNOHANG)", pid, exitcode, ru_child)
          while pid != 0:
                if pid == child_pid:
                    return exitcode, ru_child
                else:
                    logging.debug("Received unexpected SIGCHLD for PID %s", pid)
                logging.debug("again os.wait4(-1, os.WNOHANG)")
                pid, exitcode, ru_child = os.wait4(-1, os.WNOHANG)
                logging.debug("pid=%r, exitcode=%r, ru_child=%r = os.wait4(-1, os.WNOHANG)", pid, exitcode, ru_child)

        else:
            _forward_signal(signum, child_pid, process_name)

def reset_signal_handling():
    signal.pthread_sigmask(signal.SIG_SETMASK, {})

import time

class Context():
  pass

state = Context()
state.timed_out = 0
state.term_signal = signal.SIGKILL
state.monitored_pid = 0
state.kill_after = 0
state.foreground = False

def send_sig(where, sig):
  if where == 0:
    logging.debug('signal.signal(%r, signal.SIG_IGN)', sig)
    signal.signal(sig, signal.SIG_IGN)
  logging.debug('os.kill(%r, %r)', where, sig)
  return os.kill(where, sig)

import ctypes

def strsignal(sig):
  if hasattr(signal, 'strsignal'):
    return signal.strsignal(sig)
  for k, v in signal.Signals.__dict__.items():
    if k.startswith('SIG'):
      if v == sig:
        return k
  if sig == 0:
    return 'SIGZERO'
  return str(sig)

def raise_signal(sig):
  logging.debug('os.kill(0, %r)', sig)
  os.kill(0, sig)

def cleanup(sig, frame):
  logging.debug('cleanup(%s{%r}, frame)', strsignal(sig), sig)
  if state.monitored_pid:
    if sig == signal.SIGALRM:
      elapsed = time.time() - state.timeout
      logging.debug('alarm %s', elapsed)
      state.timed_out = elapsed > state.duration
      if not state.timed_out:
        return
      else:
        settimeout(0.0) # clear interval
        sig = state.term_signal
        if state.kill_after:
          saved_errno = ctypes.get_errno()  # settimeout may reset.
          # Start a new timeout after which we'll send SIGKILL.
          state.term_signal = signal.SIGKILL
          settimeout(state.kill_after, warn=False)
          state.kill_after = 0
          ctypes.set_errno(saved_errno)
    logging.info("sending signal %s{%d} to PID %s command %s", strsignal(sig), sig, state.monitored_pid, state.command)
    send_sig(state.monitored_pid, sig)
    # The normal case is the job has remained in our
    # newly created process group, so send to all processes in that.
    if not state.foreground:
      send_sig(0, sig)
      if sig != signal.SIGKILL and sig != signal.SIGCONT:
        send_sig(state.monitored_pid, signal.SIGCONT)
        send_sig(0, signal.SIGCONT)
  else: # we're the child or the child is not exec'd yet.
    import posix
    logging.info("Exiting with code %d", 128 + sig)
    posix._exit(128 + sig)

# see https://stackoverflow.com/questions/52779920/why-is-signal-sigalrm-not-working-in-python-on-windows

import math

def settimeout(duration, warn=False):
  logging.debug('settimeout(%r, warn=%r)', duration, warn)
  if duration <= 0.0:
    signal.setitimer(signal.ITIMER_REAL, 0.0, 0.0)
  else:
    #timeint = int(math.ceil(duration))
    #signal.alarm(timeint)
    state.timeout = time.time()
    state.duration = duration
    signal.setitimer(signal.ITIMER_REAL, 0.5, 0.5)

def sigaction(sig, handler, interrupt=False):
  signal.signal(sig, handler)
  signal.siginterrupt(sig, interrupt)

from pysigset import sigemptyset, sigaddset, sigdelset, sigfillset, sigismember, sigpending, sigprocmask, sigsuspend, SIGSET

def error(code, errno, msg, *args):
  logging.error("errno %s: %s", errno, msg, *args)

def unblock_signal(sig):
  unblock_set = SIGSET()
  sigemptyset(unblock_set)
  sigaddset(unblock_set, sig)
  if sigprocmask(signal.SIG_UNBLOCK, unblock_set, 0) != 0:
    error(0, ctypes.get_errno(), "warning: sigprocmask")

def chld(_sig, _frame):
  pass

def install_sigchld():
  #struct sigaction sa;
  #sigemptyset (&sa.sa_mask);  # Allow concurrent calls to handler
  handler = chld
  interrupt = True            # Restart syscalls if possible, as that's
                              # more likely to work cleanly.

  sigaction(signal.SIGCHLD, handler, interrupt=interrupt)

  # We inherit the signal mask from our parent process,
  # so ensure SIGCHLD is not blocked.
  unblock_signal(signal.SIGCHLD)

def install_cleanup(sigterm):
  sigaction(signal.SIGALRM, cleanup) # our timeout.
  sigaction(signal.SIGINT, cleanup)  # Ctrl-C at terminal for example.
  sigaction(signal.SIGQUIT, cleanup) # Ctrl-\ at terminal for example.
  sigaction(signal.SIGHUP, cleanup)  # terminal closed for example.
  sigaction(signal.SIGTERM, cleanup) # if we're killed, stop monitored proc.
  sigaction(signal.SIGINFO, cleanup)
  #sigaction(signal.SIGTSTP, cleanup)
  sigaction(signal.SIGUSR1, cleanup)
  sigaction(signal.SIGUSR2, cleanup)
  sigaction(signal.SIGVTALRM, cleanup)
  sigaction(sigterm, cleanup) # user specified termination signal.

def block_cleanup_and_chld(sigterm, old_set):
  block_set = SIGSET()
  sigemptyset(block_set)

  sigaddset(block_set, signal.SIGALRM)
  sigaddset(block_set, signal.SIGINT)
  sigaddset(block_set, signal.SIGQUIT)
  sigaddset(block_set, signal.SIGHUP)
  sigaddset(block_set, signal.SIGTERM)
  sigaddset(block_set, signal.SIGINFO)
  #sigaddset(block_set, signal.SIGTSTP)
  sigaddset(block_set, signal.SIGUSR1)
  sigaddset(block_set, signal.SIGUSR2)
  sigaddset(block_set, signal.SIGVTALRM)
  sigaddset(block_set, sigterm)

  sigaddset(block_set, signal.SIGCHLD)
  if sigprocmask(signal.SIG_BLOCK, block_set, old_set) != 0:
    error(0, ctypes.get_errno(), "warning: sigprocmask")

def parse_duration(s):
  if len(s) >= 2 and s[-1] in 's m h d'.split(' '):
    n = float(s[0:-1])
    c = s[-1]
    if c == 's':
      multiplier = 1
    elif c == 'm':
      multiplier = 60
    elif c == 'h':
      multiplier = 60 * 60
    elif c == 'd':
      multiplier = 60 * 60 * 24
    n *= multiplier
    return n
  else:
    raise ValueError("Invalid duration: {}".format(s))

EXIT_SUCCESS       = 0
EXIT_FAILURE       = 1
EXIT_TIMEDOUT      = 124   # job timed out
EXIT_CANCELED      = 125   # internal error
EXIT_CANNOT_INVOKE = 126   # error executing job
EXIT_ENOENT        = 127   # couldn't find job to exec

def disable_core_dumps():
  return False

# @cli.command()
# @click.argument('duration')
# @click.option('--preserve-status', default=False)
# @click.option('--foreground', is_flag=True)
# @click.argument('argv', nargs=-1)
# def timeout(duration, preserve_status, foreground, argv, exit=True):
#   verbose = click.get_current_context().lookup_default('verbose')
#   state.preserve_status = preserve_status
#   state.foreground = foreground
#   state.exit = exit
#   timeout = parse_duration(duration)
#   logging.info('sys.argv=%r', sys.argv)
#   logging.info('argv=%r', argv)

#   state.command = argv[0]
#   if not state.foreground:
#     os.setpgid(0, 0)

#   install_cleanup(state.term_signal)
#   signal.signal(signal.SIGTTIN, signal.SIG_IGN) # Don't stop if background child needs tty.
#   signal.signal(signal.SIGTTOU, signal.SIG_IGN) # Don't stop if background child needs tty.
#   install_sigchld() # Interrupt sigsuspend() when child exits.

#   state.monitored_pid = os.fork()
#   if state.monitored_pid < 0:
#     logging.critical("fork system call failed")
#     return EXIT_CANCELED
#   elif state.monitored_pid == 0:
#     # exec doesn't reset SIG_IGN -> SIG_DFL.
#     signal.signal(signal.SIGTTIN, signal.SIG_DFL)
#     signal.signal(signal.SIGTTOU, signal.SIG_DFL)
#     os.execvp(argv[0], argv)
#   else:
#     # We configure timers so that SIGALRM is sent on expiry.
#     # Therefore ensure we don't inherit a mask blocking SIGALRM.
#     unblock_signal(signal.SIGALRM)
#     unblock_signal(signal.SIGVTALRM)

#     settimeout(timeout, warn=True)
#     #signal.setitimer(signal.ITIMER_VIRTUAL, 0.5, 2.0)

#     # Ensure we don't cleanup() after waitpid() reaps the child,
#     # to avoid sending signals to a possibly different process.
#     state.cleanup_set = SIGSET()
#     block_cleanup_and_chld(state.term_signal, state.cleanup_set)

#     logging.info('Child PID is %s', state.monitored_pid)
#     #exitcode, ru_child = wait_for_child_and_forward_signals(state.monitored_pid, argv[0])
#     #logging.debug("Child PID %s exited with code %s", state.monitored_pid, exitcode)

#     while True:
#       logging.debug('... os.waitpid(%s, os.WNOHANG)', state.monitored_pid)
#       pid, state.status = os.waitpid(state.monitored_pid, os.WNOHANG)
#       status_sig = 0x7F & state.status
#       status_exit = (0xFF00 & state.status) >> 8
#       if 0x80 & status_exit:
#         status_exit = -(256 - status_exit)
#       logging.debug('pid{%r}, status{%r, sig=%s{%d}, exit=%r} = os.waitpid(%s, os.WNOHANG)', pid, hex(state.status), strsignal(status_sig), status_sig, status_exit, state.monitored_pid)
#       if pid != 0:
#         break
#       logging.debug('... sigsuspend(state.cleanup_set{%r})', state.cleanup_set)
#       sigsuspend(state.cleanup_set)
#       logging.debug('sigsuspend(state.cleanup_set{%r})', state.cleanup_set)

#     if pid < 0:
#       error(0, ctypes.geterrno(), "error waiting for command")
#       state.status = EXIT_CANCELED
#     else:
#       if os.WIFEXITED(state.status):
#         state.status = os.WEXITSTATUS(state.status)
#       elif os.WIFSIGNALED(state.status):
#         sig = os.WTERMSIG(state.status)
#         if os.WCOREDUMP(state.status):
#           error(0, 0, "the monitored command dumped core")
#         if state.timed_out and disable_core_dumps():
#           # exit with the signal flag set.
#           signal.signal(sig, signal.SIG_DFL)
#           unblock_signal(sig)
#           raise_signal(sig)
#         state.status = sig + 128 # what sh returns for signaled processes.
#       else:
#         # shouldn't happen
#         error(0, 0, "unknown status from command (%d)", state.status)
#         state.status = EXIT_FAILURE
#     if state.timed_out and not state.preserve_status:
#       state.status = EXIT_TIMEDOUT
#     if state.exit:
#       import posix
#       posix._exit(state.status)
#     else:
#       return state.status



# @cli.command()
# @click.argument('cmd', nargs=-1)
# def exec(cmd):
#   stdin = sys.stdin
#   stdout = sys.stdout
#   stderr = sys.stderr
#   env = os.environ
#   def grandchild():
#     reset_signal_handling()
#   try:
#     grandchild_proc = subprocess.Popen(
#       cmd,
#       stdin=stdin,
#       stdout=stdout,
#       stderr=stderr,
#       env=env,
#       close_fds=False,
#       preexec_fn=grandchild,
#       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
#     )
#   except (OSError, RuntimeError) as e:
#     logging.critical("Cannot start process: %s", e)
#     return
#   newpid = grandchild_proc.pid
#   logging.info('sys.argv=%r', sys.argv)
#   logging.info('cmd=%r', cmd)
#   logging.info('Child PID is %s', newpid)
#   exitcode, ru_child = wait_for_child_and_forward_signals(newpid, cmd[0])
#   logging.debug("Child PID %s exited with code %s", newpid, exitcode)


if __name__ == "__main__":
  cli.main(prog_name='tpudiepie', auto_envvar_prefix='TPUDIEPIE')

