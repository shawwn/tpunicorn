from invoke import task
import tpunicorn

@task(name="list")
def list_tpus(c, zone="europe-west4-a"):
  for tpu in tpunicorn.get_tpus(zone=zone):
    print(tpu['name'], tpu['state'], tpu['acceleratorType'])

