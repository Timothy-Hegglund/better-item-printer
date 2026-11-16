import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import artwork
import printer
from server import Handler

# A genuine, tiny PNG used only in a temporary test directory.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

class CalculationTests(unittest.TestCase):
    def test_all_printable_rewards_have_names(self):
        ids = artwork.required_ids()
        self.assertEqual(len(ids), 156)
        self.assertEqual(len(printer.BALLS), 25)
        self.assertTrue(all(printer.NAMES.get(str(i)) for i in ids))
        self.assertEqual(len(printer.ITEM_JUMP), 10001)
        self.assertEqual(len(printer.BALL_JUMP), 10001)
        self.assertEqual(printer.ITEM_JUMP[0], printer.ITEM_JUMP[1])

    def test_rng_initial_output_and_mask(self):
        rng = printer.RNG(1700000000)
        self.assertEqual(rng.next(), (1700000000 + 0x82A2B175229D6A5B) & printer.MASK)
        self.assertTrue(0 <= rng.a <= printer.MASK)
        for limit in (1,2,3,100,1000,10001):
            self.assertTrue(all(0 <= rng.integer(limit) < limit for _ in range(100)))

    def test_bonus_doubles_quantities(self):
        seed = 1700000000
        normal = printer.forecast(seed,0,10)
        self.assertEqual(normal['nextMode'], 0)
        bonus = printer.forecast(seed,1,10)
        self.assertEqual([x['id'] for x in normal['rewards']], [x['id'] for x in bonus['rewards']])
        self.assertEqual([2*x['count'] for x in normal['rewards']], [x['count'] for x in bonus['rewards']])

    def test_session_consumes_animation_roll(self):
        rng = printer.RNG(1700000000)
        printer.print_job(rng,0,1)
        rng.integer(100)
        expected = printer.print_job(rng,2,5)
        self.assertEqual(expected, printer.forecast(1700000000,2,5,[{'mode':0,'count':1}]))

    def test_invalid_parameters(self):
        for seed,mode,count in [(0,0,1),(printer.MAX_SEED+1,0,1),(1700000000,3,1),(1700000000,0,2)]:
            with self.assertRaises(ValueError):
                printer.forecast(seed,mode,count)

class ArtworkTests(unittest.TestCase):
    def test_complete_archive_import_and_reference_preservation(self):
        archive = BytesIO()
        with ZipFile(archive,'w') as z:
            for item_id in artwork.required_ids():
                z.writestr(f'source/Resources/bitem_{item_id}.png', PNG)
            z.writestr('source/Screenshots/reference.png', PNG)
            z.writestr('source/../../outside.png', PNG)
            z.writestr('source/program.py', 'raise Exception()')
        with tempfile.TemporaryDirectory() as directory, patch.object(artwork,'ART',Path(directory)/'art'):
            artwork.import_archive(archive.getvalue())
            status = artwork.coverage()
            self.assertTrue(status['complete'])
            self.assertEqual(status['cached'],156)
            self.assertEqual(len(status['references']),158)
            self.assertFalse((Path(directory)/'outside.png').exists())
            (artwork.ART/'items/1.png').write_bytes(b'invalid')
            self.assertEqual(artwork.coverage()['missing'],[1])

    def test_missing_sprites_fall_back_to_artwork_folder(self):
        def fake_fetch(url, maximum=0):
            if 'aitem_' in url:
                return PNG
            raise OSError('404 Not Found')
        with tempfile.TemporaryDirectory() as directory, patch.object(artwork,'ART',Path(directory)/'art'), \
                patch.object(artwork,'fetch',fake_fetch):
            artwork.fetch_missing()
            self.assertEqual(artwork.coverage()['missing'],[])

    def test_rejects_html_as_png(self):
        self.assertFalse(artwork.valid_png(b'<html>not an image</html>'))
        self.assertTrue(artwork.valid_png(PNG))

class EndpointTests(unittest.TestCase):
    def call(self,path):
        handler = Handler.__new__(Handler)
        handler.path = path
        handler.server = SimpleNamespace(phone_urls=['http://192.168.1.2:8080'],artwork_status={'complete':False})
        result = {}
        handler.respond = lambda data, code=200: result.update(data=data,code=code)
        handler.send_error = lambda code: result.update(code=code)
        handler.do_GET()
        return result

    def test_forecast_endpoint_and_validation(self):
        response = self.call('/api/forecast?seed=1700000000&mode=2&count=5')
        self.assertEqual(response['code'],200)
        self.assertEqual(len(response['data']['rewards']),5)
        self.assertEqual(self.call('/api/forecast?count=999')['code'],400)

    def test_status_has_all_156_items_and_artwork(self):
        data = self.call('/api/status')['data']
        self.assertEqual(len(data['items']),156)
        self.assertIn('artwork',data)

    def test_search_matches_requested_ball(self):
        data = self.call('/api/search?seed=1700000000&mode=2&count=1&item=1')['data']
        self.assertTrue(data['results'])
        for result in data['results']:
            self.assertEqual(result['rewards'][0]['id'],1)
            self.assertLess(result['seed'],1700003600)

    def test_search_ranks_most_master_balls_in_window(self):
        start = 1700000000
        data = self.call(f'/api/search?seed={start}&mode=2&count=10&item=1&rank=1&window=3600')['data']
        totals = [r['total'] for r in data['results']]
        best = max(sum(x['count'] for x in printer.forecast(s,2,10)['rewards'] if x['id'] == 1)
                   for s in range(start, start + 3600))
        self.assertEqual(len(totals), 8)
        self.assertEqual(totals[0], best)
        self.assertEqual(totals, sorted(totals, reverse=True))
        for result in data['results']:
            self.assertTrue(start <= result['seed'] < start + 3600)
            self.assertEqual(result['total'], sum(x['count'] for x in result['rewards'] if x['id'] == 1))
        self.assertGreaterEqual(data['matches'], 8)

    def test_search_validates_window_and_rank(self):
        self.assertEqual(self.call('/api/search?seed=1700000000&mode=2&item=1&window=86401')['code'],400)
        self.assertEqual(self.call('/api/search?seed=1700000000&mode=0&bonus=1&rank=1')['code'],400)
        short = self.call('/api/search?seed=1700000000&mode=2&count=1&item=1&window=600')['data']
        self.assertTrue(all(r['seed'] < 1700000600 for r in short['results']))

    def test_file_allowlist(self):
        for path in ['/settings.json','/printer.py','/../server.py','/art/items/../../settings.json','/art/source.json']:
            self.assertEqual(self.call(path)['code'],404)

if __name__ == '__main__':
    unittest.main()
