from six.moves import shlex_quote as shellquote
from subprocess import check_output
import json
import re
import ring
import os
import sys
import logging
import functools
import threading

import importlib
import inspect

def reload(*args):
  if not args:
    return importlib.reload(sys.modules[__name__])
  else:
    libs = [None for _ in range(len(args))]
    for i, arg in enumerate(args):
      if isinstance(arg, str):
        libs[i] = sys.modules.get(arg)
        if libs[i] is None:
          try:
            libs[i] = importlib.import_module(arg)
          except ModuleNotFoundError:
            pass
      else:
        libs[i] = arg
      if inspect.ismodule(libs[i]):
        libs[i] = importlib.reload(libs[i])
    if libs:
      if len(libs) == 1:
        return libs[0]
      return {lib.__name__: lib for lib in libs}
    

from cachier import cachier
import datetime
import requests

# https://github.com/googleapis/google-auth-library-python/issues/271#issuecomment-400186626
import warnings
warnings.filterwarnings("ignore", "Your application has authenticated using end user credentials")

import googleapiclient.discovery
#api = googleapiclient.discovery.build('tpu', 'v1alpha1')
#api_v2 = googleapiclient.discovery.build('tpu', 'v2')
#api = googleapiclient.discovery.build('tpu', 'v2alpha1', static_discovery=False, discoveryServiceUrl=googleapiclient.discovery.V2_DISCOVERY_URI)
#api = googleapiclient.discovery.build('tpu', 'v2alpha1', discoveryServiceUrl=googleapiclient.discovery.V2_DISCOVERY_URI)
api = None
api_http = None

def get_api():
  global api
  if api is None:
    api = googleapiclient.discovery.build('tpu', 'v2alpha1', discoveryServiceUrl=googleapiclient.discovery.V2_DISCOVERY_URI)
  return api

if 'logger' not in globals():
  logger = logging.getLogger('tpunicorn')

  # create console handler and set level to debug
  ch = logging.StreamHandler()
  ch.setLevel(logging.DEBUG)

  # create formatter
  formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s', datefmt='%m-%d-%Y %I:%M:%S%p %Z')
  ch.setFormatter(formatter)
  logger.addHandler(ch)

def ero(x):
  logger.info('%s', x)
  return x

def build_opt(k, v):
  k = k.rstrip('_') # support reserved words, e.g. async_
  k = k.replace('_', '-').replace('--', '_')
  if v is True:
    return '--' + k
  if v is False:
    return '--no-' + k
  return '--{} {}'.format(k, shellquote(v))

def build_commandline(cmd, tpu_name, *args, **kws):
  # if 'zone' in kws:
  #   kws['zone'] = expand_zone_abbreviations(kws['zone'])
  if is_tpu_vm(tpu_name, project=kws.get('project')) and 'tpu-vm' not in cmd or kws.get('version', '').startswith('v2'):
    cmd = cmd.replace('gcloud compute tpus', 'gcloud alpha compute tpus tpu-vm')
  return ' '.join([cmd] + [shellquote(x) for x in [tpu_name, *args]] + [build_opt(k, v) for k, v in kws.items() if v is not None])

def system(cmd, *args, **kws):
  command = build_commandline(cmd, *args, **kws)
  os.system(command)

def run(cmd, *args, **kws):
  command = build_commandline(cmd, *args, **kws)
  out = check_output(ero(command), shell=True)
  if isinstance(out, bytes):
    out = out.decode('utf8')
  return out

def parse_tpu_project(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  return fqn.split('/')[-5]

def parse_tpu_zone(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  return fqn.split('/')[-3]

def parse_tpu_id(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  return fqn.split('/')[-1]

def parse_tpu_index(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  idx = re.findall(r'([0-9]+)$', fqn)
  if len(idx) <= 0:
    idx = -1
  else:
    idx = int(idx[0])
  return idx

def parse_tpu_accelerator_type(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  accelerator_type = re.findall(r'(v[0-9]+[-][0-9]+)', fqn)
  if len(accelerator_type) <= 0:
    return "v2-8"
  else:
    return accelerator_type[0]

def parse_tpu_zone(tpu):
  fqn = tpu if isinstance(tpu, str) else tpu['name']
  if isinstance(tpu, str):
    #zone_abbreviation = re.findall(r'[-]([^-]+)[-](?:v[0-9]+[-][0-9]+)', fqn)
    # I might clean this up someday, but probably not. Sorry that this looks so cryptic.
    results = [[expand_zone_abbreviations(k), re.findall(r'\b{}\b'.format(k), fqn)] for k, v in get_zone_abbreviations(only_unambiguous_results=True).items() if len(v) <= 1]
    for zone, matched in results:
      if matched:
        return zone
  else:
    return fqn.split('/')[-3]

from collections import defaultdict

country_abbrevs = {
    'as': 'asia',
    'eu': 'europe',
    'au': 'austrailia',
    'us': 'us',
    'na': 'northamerica',
    'sa': 'southamerica',
}

region_abbrevs = {
    'n': 'north',
    's': 'south',
    'e': 'east',
    'w': 'west',
    'c': 'central',
    'ne': 'northeast',
    'nw': 'northwest',
    'se': 'southeast',
    'sw': 'southwest',
}


def get_zone_abbreviations(full_zone_names=None, only_unambiguous_results=False): # e.g. ['europe-west4-a']
  if full_zone_names is None:
    full_zone_names = get_tpu_zones()
  if isinstance(full_zone_names, str):
    full_zone_names = full_zone_names.split(',')
  results = defaultdict(lambda: [])
  for full_zone_name in full_zone_names:
    country, region, zone_id = full_zone_name.split('-')
    region, region_id = region[:-1], region[-1:]
    assert int(region_id) in list(range(10))
    for cshort, cfull in country_abbrevs.items():
      for rshort, rfull in region_abbrevs.items():
        if cfull == country and rfull == region:
          # e.g. 'euw4a'
          results[cshort + rshort + region_id + zone_id].append(full_zone_name)
          if not only_unambiguous_results:
            # e.g. 'euw4'
            results[cshort + rshort + region_id].append(full_zone_name)
            # e.g. 'euw'
            results[cshort + rshort].append(full_zone_name)
            # e.g. 'eu'
            results[cshort].append(full_zone_name)
            # e.g. '4'
            results[region_id].append(full_zone_name)
            # e.g. '4a'
            results[region_id + zone_id].append(full_zone_name)
            # e.g. 'w4'
            results[rshort + region_id].append(full_zone_name)
            # e.g. 'w'
            results[rshort].append(full_zone_name)
            # e.g. 'west4'
            results[rfull + region_id].append(full_zone_name)
            # e.g. 'west'
            results[rfull].append(full_zone_name)
  return dict(results)

def infer_zone_abbreviation(zone):
  # I might clean this up someday, but probably not. Sorry that this looks so cryptic.
  return list(get_zone_abbreviations(zone, only_unambiguous_results=True).keys())[0]

def expand_zone_abbreviations(zone):
  if zone is None:
    return zone
  results = []
  for zone in zone.split(','):
    for expansion in get_zone_abbreviations().get(zone, [zone]):
      if expansion not in results:
        results.append(expansion)
  return ','.join(results)

def get_tpu_zone_choices(project=None):
  choices = []
  for abbrev, expansions in get_zone_abbreviations().items():
    for expansion in expansions:
      if expansion not in choices:
        choices.append(expansion)
    if abbrev not in choices:
      choices.append(abbrev)
  return choices

def get_next_available_tpu_index(index, project=None, zone=None):
  tpus = get_tpus(project=project, zone=zone)
  while True:
    ok = True
    for t in tpus:
      if parse_tpu_index(t) == index:
        ok = False
        index += 1
        break
    if ok:
      return index


def parse_tpu_network(tpu):
  net = tpu if isinstance(tpu, str) else tpu['networkConfig']['network']
  return net.split('/')[-1]


def parse_tpu_subnetwork(tpu):
  net = tpu if isinstance(tpu, str) else tpu['networkConfig'].get('subnetwork', None)
  if net is not None:
    return net.split('/')[-1]


@functools.lru_cache()
def get_default_creds(creds=None):
  if creds is None:
    import google.auth
    creds, _ = google.auth.default()
  return creds

def refresh_creds(creds=None, request=None):
  creds = get_default_creds(creds)
  if request is None:
    import google.auth.transport.requests
    request = google.auth.transport.requests.Request()
  return creds.refresh(request)

def get_creds(creds=None):
  creds = get_default_creds(creds)
  if creds is not None and (creds.expired or not creds.token):
    refresh_creds(creds)
  return creds

def get_bearer_token(creds=None):
  creds = get_creds(creds)
  if creds is not None:
    return creds.token

# @ring.lru(expire=1800) # cache bearer token for 30m
# def get_bearer():
#     return check_output("gcloud auth print-access-token", shell=True).decode("utf-8").strip()


# # #@cachier(stale_after=datetime.timedelta(minutes=30))
# def get_bearer_token(creds=None):
#   creds = get_creds()
#   import google.auth
#   import google.auth.transport.requests
#   creds, project = google.auth.default()
#   if creds is None:
#     raise ValueError("Couldn't get default google auth creds; try running `gcloud auth application-default login`")
#   if creds.expired:
#     auth_req = google.auth.transport.requests.Request()
#     creds.refresh(auth_req)
#   return creds

@ring.lru(expire=3600) # cache default project for an hour
def get_default_project(project=None):
    """Determine default project ID explicitly or implicitly as fall-back.

    See :func:`google.auth.default` for details on how the default project
    is determined.

    :type project: str
    :param project: Optional. The project name to use as default.

    :rtype: str or ``NoneType``
    :returns: Default project if it can be determined.
    """
    if project is None:
        import google.auth
        _, project = google.auth.default()
    return project

def cache_clearer(x):
  if callable(x):
    if hasattr(x, 'ring') and hasattr(x, 'delete') and x.ring.__module__.split('.')[0] == 'ring':
      return lambda: x.delete()
    if hasattr(x, 'cache_clear') and x.__class__.__module__.split('.')[0] == 'functools':
      return lambda: x.cache_clear()

def uncache(x):
  if isinstance(x, list):
    return [uncache(v) for v in x]
  f = cache_clearer(x)
  if f is not None:
    f()
    return True

def reset_caches(module=__name__, matching='', exclude=''):
  if isinstance(exclude, str):
    exclude = exclude.split()
  if isinstance(matching, str):
    matching = matching.split()
  for k, v in sys.modules[module].__dict__.items():
    if matching and k not in matching:
      continue
    if exclude and k in exclude:
      continue
    if uncache(v):
      logger.info('Cache was reset: {module}.{name}'.format(module=module, name=k))

def set_active_configuration(configuration):
  if os.environ.get('CLOUDSDK_ACTIVE_CONFIG_NAME', 'default') == configuration:
    return
  logger.info('Setting CLOUDSDK_ACTIVE_CONFIG_NAME=%s', configuration)
  os.environ['CLOUDSDK_ACTIVE_CONFIG_NAME'] = configuration
  reset_caches()
  return True
  

@cachier(stale_after=datetime.timedelta(days=3))
def fetch_tpu_zones(project):
  print('Fetching TPU zones...', file=sys.stderr)
  zones = get_api().projects().locations().list(name='projects/'+project).execute().get('locations', [])
  return [zone['locationId'] for zone in zones]

#@ring.lru(expire=3600) # cache tpu zones for an hour
def get_tpu_zones(project=None):
  project = get_default_project(project=project)
  if project is None:
    # punt with some default TPU zones.
    return 'asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f'.split('|')
  else:
    return fetch_tpu_zones(project=project)

from concurrent import futures

@ring.lru(expire=5) # cache tpu info for 5 seconds
def fetch_tpus(zone=None, project=None):
  # if zone is None:
  #   zones = get_tpu_zones(project=project)
  # if isinstance(zone, str):
  #   zones = zone.split(',')
  # tpus = []
  # session = get_requests_session()
  # #with futures.ThreadPoolExecutor() as executor:
  # if True:
  #   import builtins as executor
  #   for nodes in executor.map(lambda zone: list_tpus(zone, project=project, session=session), zones):
  #     tpus.extend(nodes)
  # return tpus
  return list_tpus(zone=zone, project=project)

# this is very slow. Special-case it for speed.
# def list_tpus(zone, project=None):
#   if '/' not in zone:
#     zone = 'projects/' + get_default_project(project=project) + '/locations/' + zone
#   tpus = get_api().projects().locations().nodes().list(parent=zone).execute().get('nodes', [])
#   return list(sorted(tpus, key=parse_tpu_index))

@ring.lru()
def get_cached_requests_session():
  return requests.Session()

def get_requests_session(session=None):
  if session is None:
    session = get_cached_requests_session()
  elif session is False:
    session = requests
  return session

def get_headers(headers=None, project=None):
  project = get_default_project(project)
  defaults = {
      'accept': 'application/json',
      'accept-encoding': 'gzip, deflate',
      'authorization': 'Bearer ' + get_bearer_token(),
      'content-length': '0',
      'user-agent': '(gzip)',
      'x-goog-api-client': 'gdcl/2.7.0 gl-python/3.9.5',
      'x-goog-user-project': project}
  if headers is not None:
    defaults.update(headers)
  return defaults

def build_endpoint_url(api='tpu', version='v2alpha1', **parts):
  url = 'https://{api}.googleapis.com/{version}/'.format(api=api, version=version)
  for name, value in parts.items():
    if value is True:
      return url + name + '?alt=json'
    if value is None:
      if name == 'projects':
        value = get_default_project()
      raise ValueError(name + " was None; don't know how to get default value")
    if value is None or value is False:
      continue
    url += name + '/' + value + '/'
  raise ValueError("The last keyword arg should be True, but wasn't")


from urllib.parse import urlparse

import braceexpand

def bracify(**kws):
  results = []
  for k, v in kws.items():
    if isinstance(v, (tuple, list)):
      results.append([k, '{' + ','.join(v) + '}'])
    else:
      results.append([k, v])
  return dict(results)
  
def request_urls(path, api='tpu', apiVersion='v2alpha1', **kws):
  if '/' not in path:
    *parts, resource = path.split('.')
    replacements = {'location': 'zone'}
    path = '/'.join(['/'.join([part, '{' + replacements.get(part[:-1], part[:-1]) + '}']) for part in parts] + [resource])
  url = 'https://{api}.googleapis.com/{apiVersion}/' + path
  return list(braceexpand.braceexpand(url.format(api=api, apiVersion=apiVersion, **bracify(**kws))))

from concurrent import futures

def request(path, api='tpu', apiVersion=None, headers=None, session=None, project=None, **kws):
  if apiVersion is None:
    if api == 'tpu':
      apiVersion = 'v2alpha1'
    else:
      apiVersion = 'v1'
  session = get_requests_session(session=session)
  project = get_default_project(project=project)
  headers = get_headers(headers=headers, project=project)
  urls = request_urls(path, api=api, apiVersion=apiVersion, project=project, **kws)
  def fetcher(url):
    req = session.get(url, headers=headers)
    req.raise_for_status()
    res = req.json()
    return res
    # key = urlparse(url).path.rsplit('/', 1)[-1]
    # return res.get(key, [])
  with futures.ThreadPoolExecutor() as executor:
    result = []
    for res in executor.map(fetcher, urls):
      result.append(res)
    if len(result) <= 1:
      return result[0]
    return result

def api_list_locations_url(project=None):
  project = get_default_project(project=project)
  return 'https://tpu.googleapis.com/v2alpha1/projects/{project}/locations?alt=json'.format(project=project)

def api_list_locations(project=None, session=None):
  url = api_list_locations_url(project=project)
  session = get_requests_session(session=session)
  project = get_default_project(project=project)
  headers = get_headers(headers=None, project=project)
  response = session.get(url, headers=headers).json()
  return response.get('locations', [])

def api_list_nodes_url(zone, project=None):
  project = get_default_project(project=project)
  return 'https://tpu.googleapis.com/v2alpha1/projects/{project}/locations/{zone}/nodes?alt=json'.format(project=project, zone=zone)

def api_list_nodes(zone, project=None, session=None):
  url = api_list_nodes_url(zone=zone, project=project)
  session = get_requests_session(session=session)
  project = get_default_project(project=project)
  headers = get_headers(headers=None, project=project)
  response = session.get(url, headers=headers).json()
  return response.get('nodes', [])

def api_zones(project=None, session=None):
  return [x['locationId'] for x in api_list_locations(project=project, session=session)]

import concurrent.futures
import operator
import functools

def list_tpus(zone=None, project=None, session=None):
  if zone is None:
    zone = api_zones(project=project, session=session)
    tpus = functools.reduce(operator.concat,
        [x.get('nodes', []) for x in 
          request('projects.locations.nodes', zone=zone, project=project, session=session)])
  else:
    tpus = request('projects.locations.nodes', zone=zone, project=project, session=session).get('nodes', [])
  # with concurrent.futures.ThreadPoolExecutor() as executor:
  #   zones = [x['locationId'] for x in api_list_locations()]
  #   tpus = functools.reduce(operator.concat, executor.map(api_list_nodes, zones))
  return list(sorted(tpus, key=parse_tpu_index))

def get_tpus(zone=None, project=None):
  tpus = fetch_tpus(zone=zone, project=project)
  # if zone is None:
  #   return tpus
  # else:
  #   return [tpu for tpu in tpus if '/{}/'.format(zone) in tpu['name']]
  return tpus

def get_tpu(tpu, zone=None, project=None, silent=False):
  if isinstance(tpu, dict):
    tpu = parse_tpu_id(tpu)
  if isinstance(tpu, str) and re.match('^[0-9]+$', tpu):
    tpu = int(tpu)
  if isinstance(tpu, int):
    which = 'index'
    tpus = [x for x in get_tpus(zone=zone, project=project) if parse_tpu_index(x) == tpu]
  else:
    which = 'id'
    tpus = [x for x in get_tpus(zone=zone, project=project) if parse_tpu_id(x) == tpu]
  if len(tpus) > 1:
    raise ValueError("Multiple TPUs matched {} {!r}. Try specifying --zone".format(which, tpu))
  if len(tpus) <= 0:
    if silent:
      return None
    raise ValueError("No TPUs matched {} {!r}".format(which, tpu))
  return tpus[0]

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

@ring.lru(expire=1) # seconds
def format_widths(project=None):
  headers = format_headers()
  tpus = get_tpus(project=project)
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
import datetime
import time

def get_timestamp(timestamp=None, utc=True):
  if timestamp is None:
    timestamp = time.time()
  # https://stackoverflow.com/a/52606421/9919772
  #dt = datetime.datetime.fromtimestamp(timestamp).astimezone()
  dt = moment.unix(timestamp, utc=utc)
  dt = dt.timezone(current_tzname())
  return dt.strftime("%m-%d-%Y %I:%M:%S%p %Z")

def current_timezone():
  if time.daylight:
    return datetime.timezone(datetime.timedelta(seconds=-time.altzone),time.tzname[1])
  else:
    return datetime.timezone(datetime.timedelta(seconds=-time.timezone),time.tzname[0])

def current_tzname():
  return current_timezone().tzname(None)

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
  out = False
  if d > 0 or out:
    out = True
    r += ['{:02d}d'.format(d)]
  else:
    r += ['   ']
  if h > 0 or out:
    out = True
    r += ['{:02d}h'.format(h)]
  else:
    r += ['   ']
  if m > 0 or out:
    out = True
    r += ['{:02d}m'.format(m)]
  else:
    r += ['   ']
  # if s > 0 or out:
  #   out = True
  #   r += ['{:02d}s'.format(s)]
  return ''.join(r)

def format_headers():
  return {
    'kind': 'header',
    'project': 'PROJECT',
    'zone': 'ZONE',
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
    'version': 'VERSION',
    'network': 'NETWORK',
    'subnetwork': 'SUBNETWORK',
  }

def _format_args(tpu):
  return {
    'kind': 'tpu',
    'project': parse_tpu_project(tpu),
    'zone': parse_tpu_zone(tpu),
    'id': parse_tpu_id(tpu),
    'fqn': tpu['name'],
    'ip': parse_tpu_ip(tpu),
    'port': parse_tpu_port(tpu),
    'master': parse_tpu_master(tpu),
    'range': parse_tpu_range(tpu),
    'type': parse_tpu_type(tpu),
    'created': tpu['createTime'],
    'age': nice_since(tpu['createTime']),
    'preemptible': 'yes' if parse_tpu_preemptible(tpu) else 'no',
    'status': tpu['state'],
    'health': tpu.get('health', 'UNKNOWN'),
    'index': parse_tpu_index(tpu),
    'version': parse_tpu_version(tpu),
    'network': parse_tpu_network(tpu),
    'subnetwork': parse_tpu_subnetwork(tpu),
  }

def parse_tpu_preemptible(tpu):
  return tpu.get('schedulingConfig', {'preemptible': False}).get('preemptible', False)

def parse_tpu_ip(tpu, internal_only=False):
  master = tpu['networkEndpoints'][0]
  external_ip = master.get('accessConfig', {}).get('externalIp', None)
  internal_ip = master.get('ipAddress', None)
  if internal_only:
    return internal_ip
  return external_ip

def parse_tpu_port(tpu):
  master = tpu['networkEndpoints'][0]
  return master.get('port', None)

def parse_tpu_master(tpu, internal_only=True):
  return '{}:{}'.format(
    parse_tpu_ip(tpu, internal_only=internal_only),
    parse_tpu_port(tpu))

def parse_tpu_range(tpu):
  return tpu.get('cidrBlock', None)

def parse_tpu_version(tpu):
  return tpu['runtimeVersion']

def parse_tpu_type(tpu):
  return tpu['acceleratorType']

def parse_tpu_description(tpu):
  return tpu.get('description', None)

def parse_tpu_data_disks(tpu):
  return tpu.get('dataDisks', [])

def parse_tpu_data_disk(tpu, disk_index=0):
  disks = parse_tpu_data_disks(tpu)
  if disk_index >= 0 and disk_index < len(disks):
    disk = disks[disk_index]
    return 'source={source},mode={mode}'.format(
      source=disk['sourceDisk'],
      mode=disk['mode'].lower().replace('_', '-')
    )

def is_tpu_vm(tpu, project=None):
  tpu = get_tpu(tpu, silent=True, project=project)
  return tpu is not None and parse_tpu_version(tpu).startswith('v2')

def format_args(tpu, project=None):
  r = _format_args(tpu)
  r.update(format_widths(project=project))
  return r

def get_default_format_specs(thin=False):
  specs = [
    "{zone:{zone_w}}",
    "{index:<{index_w}}",
    "{type:{type_w}}",
    "{age:{age_w}}",
    "{id:{id_w}}",
    "{status:{status_w}}",
    "{health:{health_w}}",
    "{version:{version_w}}",
    "{network:{network_w}}",
    "{master:{master_w}}",
    "{range:{range_w}}",
    "{preemptible!s:{preemptible_w}}",
  ]
  if thin:
    return ['{' + re.findall('{([^:]+)[:]', x)[0] + '}' for x in specs]
  else:
    return specs

def get_default_format_spec(thin=False):
  return ' '.join(get_default_format_specs(thin=thin))

def format(tpu, spec=None, formatter=NamespaceFormatter, project=None):
  if tpu.get('kind', 'tpu') == 'tpu':
    args = format_args(tpu, project=project)
  else:
    args = {}
    args.update(tpu)
    args.update(format_widths(project=project))
  args = {k: v if v is not None else '' for k, v in args.items()}
  fmt = formatter(args)
  if spec is None:
    spec = get_default_format_spec(thin=len(format_widths(project=project)) == 0)
  return fmt.format(spec)

def create_tpu_command(tpu=None, zone=None, version=None, accelerator_type=None, project=None, description=None, network=None, subnetwork=None, range=None, preemptible=None, async_=False, data_disk=None):
  name = parse_tpu_id(tpu)
  if not isinstance(tpu, str):
    if zone is None:
      zone = parse_tpu_zone(tpu)
    if project is None:
      project = parse_tpu_project(tpu)
    if version is None:
      version = parse_tpu_version(tpu)
    if accelerator_type is None:
      accelerator_type = parse_tpu_type(tpu)
    if description is None:
      description = parse_tpu_description(tpu)
    if preemptible is None:
      preemptible = True if parse_tpu_preemptible(tpu) else None
    if network is None:
      network = parse_tpu_network(tpu)
    if subnetwork is None:
      subnetwork = parse_tpu_subnetwork(tpu)
    if range is None:
      range = parse_tpu_range(tpu)
    if data_disk is None:
      data_disk = parse_tpu_data_disk(tpu)
  if data_disk is not None:
    if project is None or zone is None:
      raise ValueError("When --data-disk is specified, you must also specify --zone and --project")
    if 'source=' not in data_disk:
      data_disk = 'source=projects/{project}/zones/{zone}/disks/{disk}'.format(
        project=project,
        zone=zone,
        disk=data_disk,
      )
    if 'mode=' not in data_disk:
      if ',' in data_disk:
        disk_mode = data_disk.rsplit(',')[-1]
      else:
        disk_mode = 'read-write'
      data_disk += ',mode=' + disk_mode.lower().replace('_', '-')
  return build_commandline("gcloud compute tpus create",
                           name,
                           zone=zone,
                           project=project,
                           network=network,
                           subnetwork=subnetwork,
                           range=range,
                           version=version,
                           accelerator_type=accelerator_type,
                           preemptible=preemptible,
                           description=description,
                           async_=async_,
                           data_disk=data_disk,
                           )

def delete_tpu_command(tpu, zone=None, project=None, async_=False):
  if zone is None:
    zone = parse_tpu_zone(tpu)
  if project is None:
    project = parse_tpu_project(tpu)
  return build_commandline("gcloud compute tpus delete",
                           parse_tpu_id(tpu),
                           zone=zone,
                           project=project,
                           quiet=True,
                           async_=async_,
                           )

def start_tpu_command(tpu, zone=None, project=None, async_=False):
  if zone is None:
    zone = parse_tpu_zone(tpu)
  if project is None:
    project = parse_tpu_project(tpu)
  return build_commandline("gcloud compute tpus start",
                           parse_tpu_id(tpu),
                           zone=zone,
                           project=project,
                           quiet=True,
                           async_=async_,
                           )

def stop_tpu_command(tpu, zone=None, project=None, async_=False):
  if zone is None:
    zone = parse_tpu_zone(tpu)
  if project is None:
    project = parse_tpu_project(tpu)
  return build_commandline("gcloud compute tpus stop",
                           parse_tpu_id(tpu),
                           zone=zone,
                           project=project,
                           quiet=True,
                           async_=async_,
                           )

def reimage_tpu_command(tpu, zone=None, project=None, version=None, async_=False):
  if zone is None:
    zone = parse_tpu_zone(tpu)
  if project is None:
    project = parse_tpu_project(tpu)
  if version is None:
    version = parse_tpu_version(tpu)
  return build_commandline("gcloud compute tpus reimage",
                           parse_tpu_id(tpu),
                           zone=zone,
                           project=project,
                           version=version,
                           quiet=True,
                           async_=async_,
                           )

def ssh_tpu_command(tpu, zone=None, project=None, ssh_flag=None):
  if zone is None:
    zone = parse_tpu_zone(tpu)
  if project is None:
    project = parse_tpu_project(tpu)
  return build_commandline("gcloud alpha compute tpus tpu-vm ssh",
                           parse_tpu_id(tpu),
                           zone=zone,
                           project=project,
                           ssh_flag=ssh_flag,
                           )
