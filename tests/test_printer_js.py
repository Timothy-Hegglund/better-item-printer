"""Checks the browser port (web/printer.js, used on GitHub Pages) against the Python calculation."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from printer import forecast
import server

WEB = Path(__file__).resolve().parent.parent / 'web'
CASES = [(seed, mode, count, chain) for seed in (946684800, 1700000000, 1731700000, 2871763199)
         for mode in (0, 1, 2) for count in (1, 5, 10)
         for chain in ([], [{'mode': 0, 'count': 10}, {'mode': 1, 'count': 5}])]
SEARCHES = [dict(seed=1700000000, mode=0, count=10, item=0, bonus=2, rank=0, window=3600),
            dict(seed=1700000000, mode=2, count=10, item=1, bonus=0, rank=1, window=7200)]
NODE = """
const fs = require('fs'), path = require('path'), web = process.argv[1];
globalThis.location = {href: 'https://example.github.io/app/'};
globalThis.fetch = async url => ({json: async () => JSON.parse(fs.readFileSync(path.join(web, url), 'utf8'))});
const {localApi} = require(path.join(web, 'printer.js'));
(async () => {
  const [cases, searches] = JSON.parse(fs.readFileSync(0, 'utf8')), out = {forecasts: [], searches: []};
  for (const [seed, mode, count, chain] of cases)
    out.forecasts.push(await localApi('forecast', {seed, mode, count, chain: JSON.stringify(chain)}));
  for (const s of searches) out.searches.push(await localApi('search', s));
  out.status = await localApi('status', {});
  console.log(JSON.stringify(out));
})();
"""

@unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
class BrowserPortTests(unittest.TestCase):
    def test_js_matches_python(self):
        run = subprocess.run(['node', '-e', NODE, str(WEB)], input=json.dumps([CASES, SEARCHES]),
                             capture_output=True, text=True, check=True)
        out = json.loads(run.stdout)
        for (seed, mode, count, chain), js in zip(CASES, out['forecasts']):
            py = forecast(seed, mode, count, chain)
            self.assertEqual((js['rewards'], js['nextMode']), (py['rewards'], py['nextMode']), (seed, mode, count, chain))
        for params, js in zip(SEARCHES, out['searches']):
            py = self.python_search(params)
            self.assertEqual(js, py, params)
            self.assertTrue(js['results'])
        self.assertEqual(len(out['status']['items']), 156)

    def python_search(self, params):
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/search?' + '&'.join(f'{k}={v}' for k, v in params.items())
        captured = {}
        handler.respond = lambda obj, code=200: captured.update(obj)
        handler.do_GET()
        return captured
