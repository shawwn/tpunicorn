from invoke.vendor.six.moves import shlex_quote as shellquote
from subprocess import check_output
import invoke
import json
import re
import ring
import sys


def ero(*args):
  print(*args, file=sys.stderr)
  if len(args) > 0:
    return args[0]


def run(cmd, *args, **kws):
  command = ' '.join([cmd] + [shellquote(x) for x in args] + ['--{} {}'.format(k, shellquote(v)) for k, v in kws.items()])
  out = invoke.run(ero(command), hide="out").stdout
  #out = check_output(ero(command), shell=True)
  return out


def parse_tpu_index(tpu):
  name = tpu if isinstance(tpu, str) else tpu['name']
  idx = re.findall(r'[-]([0-9]+)$', name)
  if len(idx) <= 0:
    idx = -1
  else:
    idx = int(idx[0])
  return idx


@ring.lru(expire=5) # seconds
def get_tpus(zone):
  out = run("gcloud compute tpus list", format="json", zone=zone)
  tpus = json.loads(out)
  return sorted(tpus, key=parse_tpu_index)

