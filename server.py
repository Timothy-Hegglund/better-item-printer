"""Run the printer on your PC; open the displayed LAN address on your phone."""
import argparse
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import heapq
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit, parse_qs
import webbrowser
import re
import artwork
from printer import forecast, ITEMS, BALLS, NAMES, MAX_SEED

ROOT = Path(__file__).resolve().parent / 'web'

def clock():
    now = datetime.now()
    return {'unixMs': time.time_ns() // 1_000_000,
            'seed': int((now - datetime(1970, 1, 1)).total_seconds()),
            'local': now.isoformat(timespec='milliseconds')}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith(('GET /api/', 'GET /favicon', 'GET /art/')):
            return
        super().log_message(fmt, *args)

    def respond(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if not url.path.startswith('/api/'):
            if url.path not in ('/', '/index.html', '/style.css', '/app.js', '/printer.js') and not re.fullmatch(r'/art/(?:items/\d+\.png|references/\d+\.(?:png|jpg|jpeg|gif|webp|bmp|ico|svg|avif|tif|tiff))', url.path):
                self.send_error(404)
                return
            return super().do_GET()
        try:
            q = parse_qs(url.query)
            value = lambda key, default: int(q.get(key, [default])[0])
            current = clock()
            if url.path == '/api/status':
                return self.respond({**current, 'urls': self.server.phone_urls,
                    'artwork': self.server.artwork_status,
                    'items': [{'id': x['ItemId'], 'name': NAMES[str(x['ItemId'])], 'ball': ball}
                              for ball, entries in ((False, ITEMS), (True, BALLS)) for x in entries]})
            seed, mode, count = value('seed', current['seed']), value('mode', 0), value('count', 10)
            chain = json.loads(q.get('chain', ['[]'])[0])
            if not isinstance(chain, list) or len(chain) > 100:
                raise ValueError('A session can contain up to 100 jobs.')
            if url.path == '/api/forecast':
                return self.respond({**current, 'forecastSeed': seed, **forecast(seed, mode, count, chain)})
            if url.path == '/api/search':
                item, bonus, rank, window = value('item', 0), value('bonus', 0), value('rank', 0), value('window', 3600)
                if not 60 <= window <= 86400:
                    raise ValueError('Choose a time frame between 1 minute and 24 hours.')
                if not item and bonus not in (1, 2):
                    raise ValueError('Choose an item or a bonus to find.')
                if rank and not item:
                    raise ValueError('Choose a desired item to rank times by quantity.')
                if bonus and mode != 0:
                    raise ValueError('Bonus activation can only be searched in Regular mode.')
                if item and not any(x['ItemId'] == item for x in (BALLS if mode == 2 else ITEMS)):
                    raise ValueError('That item is unavailable in this mode.')
                hits = []  # (total of desired item, -seed): keeps memory small for 24-hour scans
                for candidate in range(seed, min(seed + window, MAX_SEED + 1)):
                    result = forecast(candidate, mode, count)
                    total = sum(x['count'] for x in result['rewards'] if x['id'] == item)
                    if (not bonus or result['nextMode'] == bonus) and (not item or total):
                        hits.append((total, -candidate))
                        if not rank and len(hits) == 8:
                            break
                matches = len(hits)
                if rank:  # most of the item first; ties go to the earliest time
                    hits = heapq.nlargest(8, hits)
                return self.respond({'matches': matches, 'results': [
                    {'seed': -s, 'total': total, **forecast(-s, mode, count)} for total, s in hits]})
            self.send_error(404)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            self.respond({'error': str(exc)}, 400)


def lan_urls(port):
    addresses = set()
    try:
        addresses.update(x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return [f'http://{ip}:{port}' for ip in sorted(addresses) if not ip.startswith(('127.', '169.254.'))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        raise SystemExit(f'Cannot open port {args.port}: {exc}. Try --port 8081.')
    server.artwork_status = artwork.prepare()
    NAMES.update(json.loads((ROOT / 'data/names.json').read_text(encoding='utf-8')))
    server.phone_urls = lan_urls(server.server_port)
    print(f'\nBetter Item Printer\nPC: http://localhost:{server.server_port}', flush=True)
    for url in server.phone_urls:
        print(f'Phone (same Wi-Fi): {url}', flush=True)
    print('Keep this window open. Ctrl+C stops the server.\nIf Windows asks, allow access on Private networks.\n', flush=True)
    if not args.no_browser:
        webbrowser.open(f'http://localhost:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
