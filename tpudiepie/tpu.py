from subprocess import check_output
import json
import re
import ring

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
  out = check_output("gcloud compute tpus list --format json".split(' ') + ["--zone", zone])
  tpus = json.loads(out)
  return sorted(tpus, key=parse_tpu_index)

