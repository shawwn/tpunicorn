from six.moves import shlex_quote as shellquote
from subprocess import check_output
import json
import re
import ring
import sys
from pprint import pprint as pp


def ero(*args):
  print(*args, file=sys.stderr)
  if len(args) > 0:
    return args[0]


def build_commandline(cmd, *args, **kws):
  return ' '.join([cmd] + [shellquote(x) for x in args] + ['--{} {}'.format(k, shellquote(v)) for k, v in kws.items()])


def run(cmd, *args, **kws):
  command = build_commandline(cmd, *args, **kws)
  #out = invoke.run(ero(command), hide="out").stdout
  out = check_output(ero(command), shell=True)
  return out


def parse_tpu_index(tpu):
  name = tpu if isinstance(tpu, str) else tpu['name']
  idx = re.findall(r'[-]([0-9]+)$', name)
  if len(idx) <= 0:
    idx = -1
  else:
    idx = int(idx[0])
  return idx

def get_tpu_zones():
  return ["europe-west4-a", "us-central1-f", "us-central1-a"]

@ring.lru(expire=15) # seconds
def get_tpus(zone=None):
  if zone is None:
    tpus = []
    for zone in get_tpu_zones():
      tpus.extend(get_tpus(zone=zone))
    return tpus
  else:
    out = run("gcloud compute tpus list", format="json", zone=zone)
    tpus = json.loads(out)
    return sorted(tpus, key=parse_tpu_index)

from string import Formatter

class NamespaceFormatter(Formatter):
  def __init__(self, namespace={}):
    Formatter.__init__(self)
    self.namespace = namespace

  def get_value(self, key, args, kwds):
    if isinstance(key, str):
      try:
        # Check explicitly passed arguments first
        return kwds[key]
      except KeyError:
        return self.namespace[key]
    else:
      return Formatter.get_value(key, args, kwds)

from collections import defaultdict

@ring.lru(expire=60) # seconds
def format_widths():
  headers = format_headers()
  tpus = get_tpus()
  r = defaultdict(int)
  for tpu in tpus:
    args = _format_args(tpu)
    for k, v in args.items():
      s = '{}'.format(v)
      r[k+'_w'] = max(r[k+'_w'], len(s) + 1, len(headers[k]) + 1)
  return r

def _normalize_tpu_isodate(iso):
  r = re.findall('(.*[.][0-9]{6})[0-9]*Z', iso)
  if len(r) > 0:
    return r[0] + 'Z'
  raise ValueError("Could not parse TPU date {!r}".format(iso))

import moment

def since(iso):
  dt = moment.utcnow() - moment.utc(_normalize_tpu_isodate(iso), "%Y-%m-%dT%H:%M:%S.%fZ")
  return dt.total_seconds()

def minutes_since(iso):
  return since(iso) / 60

def hours_since(iso):
  return since(iso) / 3600

def days_since(iso):
  return since(iso) / 86400

def nice_since(iso):
  t = int(since(iso))
  s = t % 60
  m = (t // 60) % 60
  h = (t // 3600) % 24
  d = (t // 86400)
  r = []
  out = True
  if d > 0:
    out = True
    r += ['{:02d}d'.format(d)]
  if h > 0 or out:
    out = True
    r += ['{:02d}h'.format(h)]
  if m > 0 or out:
    out = True
    r += ['{:02d}m'.format(m)]
  if s > 0 or out:
    out = True
    r += ['{:02d}s'.format(s)]
  return ','.join(r)

def format_headers():
  return {
    'kind': 'HEADER',
    'id': 'ID',
    'fqn': 'FQN',
    'ip': 'IP',
    'port': 'PORT',
    'master': 'MASTER',
    'range': 'RANGE',
    'type': 'TYPE',
    'created': 'CREATED',
    'age': 'AGE',
    'preemptible': 'PREEMPTIBLE?',
    'status': 'STATUS',
    'health': 'HEALTH',
    'index': 'INDEX',
  }

def _format_args(tpu):
  preemptible = tpu.get('schedulingConfig', {'preemptible': False}).get('preemptible', False)
  return {
    'kind': 'tpu',
    'id': tpu['name'].split('/')[-1],
    'fqn': tpu['name'],
    'ip': tpu['ipAddress'],
    'port': tpu['port'],
    'master': '{}:{}'.format(tpu['ipAddress'], tpu['port']),
    'range': tpu['cidrBlock'],
    'type': tpu['acceleratorType'],
    'created': tpu['createTime'],
    'age': nice_since(tpu['createTime']),
    'preemptible': 'yes' if preemptible else 'no',
    'status': tpu['state'],
    'health': tpu.get('health', 'UNKNOWN'),
    'index': parse_tpu_index(tpu),
  }

def format_args(tpu):
  r = _format_args(tpu)
  r.update(format_widths())
  return r

def format(tpu, spec="{index:<{index_w}} {type:{type_w}} {age:>{age_w}}  {id:{id_w}} {status:{status_w}} {health:{health_w}} {master:{master_w}} {range:{range_w}} {preemptible!s:{preemptible_w}}", formatter=NamespaceFormatter):
  #pp(tpu)
  if tpu.get('kind', 'tpu') == 'tpu':
    args = format_args(tpu)
  else:
    args = {}
    args.update(tpu)
    args.update(format_widths())
  fmt = formatter(args)
  return fmt.format(spec)
