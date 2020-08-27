import os
import sys
from sanic import Sanic
from sanic.response import json, text

import tpunicorn

app = Sanic()

@app.route('/.json')
async def tpus(request):
    return json(tpunicorn.get_tpus())

@app.route('/')
async def tpus(request):
  s = tpunicorn.format(tpunicorn.format_headers()) + '\n'
  for tpu in tpunicorn.get_tpus():
    s += tpunicorn.format(tpu) + '\n'
  return text(s)
    
if __name__ == '__main__':
  args = sys.argv[1:]
  port = int(args[0] if len(args) > 0 else os.environ.get('PORT', '8000'))
  app.run(host='0.0.0.0', port=port)
