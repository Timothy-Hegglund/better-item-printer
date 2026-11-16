"""Cache original artwork, with an explicit completeness report. No packages needed."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import re
import struct
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'web' / 'art'
SOURCE = 'https://codeload.github.com/kwsch/ItemPrinterDeGacha/zip/refs/heads/main'
FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.svg', '.avif', '.tif', '.tiff'}
PNG = b'\x89PNG\r\n\x1a\n'


def required_ids():
    items = json.loads((ROOT / 'web/data/items.json').read_text())['Table']
    balls = json.loads((ROOT / 'web/data/balls.json').read_text())['Table']
    return sorted({x['Param']['Value']['ItemId'] for x in items} |
                  {x['ItemId'] for group in balls for x in group['Param']['Table']})


def valid_png(data):
    if len(data) < 33 or not data.startswith(PNG) or data[12:16] != b'IHDR':
        return False
    width, height = struct.unpack('>II', data[16:24])
    return 0 < width <= 8192 and 0 < height <= 8192 and b'IEND' in data[-16:]


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    temp.replace(path)


def fetch(url, maximum=32 * 1024 * 1024):
    request = Request(url, headers={'User-Agent': 'BetterItemPrinter/1.0', 'Accept': '*/*'})
    with urlopen(request, timeout=25) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Artwork download exceeded its size limit.')
    return data


def coverage():
    missing = []
    for item_id in required_ids():
        path = ART / 'items' / f'{item_id}.png'
        if not path.exists() or not valid_png(path.read_bytes()):
            missing.append(item_id)
    refs = ART / 'references.json'
    try:
        references = json.loads(refs.read_text(encoding='utf-8')) if refs.exists() else []
    except (ValueError, OSError):
        references = []
    return {'total': len(required_ids()), 'cached': len(required_ids()) - len(missing),
            'missing': missing, 'references': references,
            'complete': not missing and (ART / 'source.json').exists()}


def import_archive(data):
    """Copy artwork only, never extract paths or executable content from the archive."""
    desired = set(required_ids())
    references, candidates = [], {}
    with ZipFile(BytesIO(data)) as archive:
        if sum(x.file_size for x in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError('Artwork archive is too large.')
        for member in sorted(archive.infolist(), key=lambda x: x.filename):
            path = Path(member.filename)
            if path.suffix.lower() not in FORMATS or member.is_dir():
                continue
            if member.file_size > 4 * 1024 * 1024:
                continue
            image_data = archive.read(member)
            # Preserve every source image as reference art, with a safe generated name.
            filename = f'{len(references):04d}{path.suffix.lower()}'
            atomic_write(ART / 'references' / filename, image_data)
            references.append({'name': '/'.join(path.parts[1:]), 'url': '/art/references/' + filename})
            match = re.fullmatch(r'(?:bitem_|item_|item|_)?(\d+)\.png', path.name, re.IGNORECASE)
            if match and int(match[1]) in desired and valid_png(image_data):
                item_id = int(match[1])
                # Prefer the original bitem sprites over any incidental numeric filenames.
                priority = 0 if path.name.startswith('bitem_') else 1
                if item_id not in candidates or priority < candidates[item_id][0]:
                    candidates[item_id] = (priority, image_data)
        for item_id, (_, image_data) in candidates.items():
            atomic_write(ART / 'items' / f'{item_id}.png', image_data)
        # Use the original, unnormalized text: line index equals national item ID.
        for member in archive.infolist():
            if member.filename.endswith('/Resources/text/items_en.txt'):
                names = archive.read(member).decode('utf-8-sig').splitlines()
                if len(names) > max(desired):
                    mapped = {str(i): names[i] for i in desired if names[i]}
                    if len(mapped) == len(desired):
                        atomic_write(ROOT / 'web/data/names.json', json.dumps(mapped, ensure_ascii=False).encode())
                break
    atomic_write(ART / 'references.json', json.dumps(references, ensure_ascii=False).encode())
    atomic_write(ART / 'source.json', json.dumps({'source': SOURCE, 'images': len(references)}).encode())


# Gen 9 items (Tera Shards, Teacups, Covert Cloak…) exist only as "Artwork Items" sprites in PKHeX.
# shortcut: fixed PKHeX folder names (avoids the rate-limited GitHub API); update if PKHeX renames them.
SPRITES = ('PKHeX.Drawing.PokeSprite/Resources/img/Big%20Items/bitem_{}.png',
           'PKHeX.Drawing.PokeSprite/Resources/img/Artwork%20Items/aitem_{}.png')
MIRRORS = ('https://raw.githubusercontent.com/kwsch/PKHeX/master/',
           'https://cdn.jsdelivr.net/gh/kwsch/PKHeX@master/')


def fetch_missing():
    """Download each missing sprite from PKHeX: small sprite, then artwork sprite; GitHub, then jsDelivr."""
    def download(item_id):
        problems = []
        for mirror in MIRRORS:
            for path in SPRITES:
                url = mirror + path.format(item_id)
                try:
                    data = fetch(url, 4 * 1024 * 1024)
                    if valid_png(data):
                        atomic_write(ART / 'items' / f'{item_id}.png', data)
                        return None
                    problems.append(f'{url}: invalid PNG')
                except Exception as exc:
                    problems.append(f'{url}: {exc}')
        return f'{item_id}: ' + '; '.join(problems)
    with ThreadPoolExecutor(max_workers=6) as pool:
        for problem in pool.map(download, coverage()['missing']):
            if problem:
                print('Artwork download failed:', problem, flush=True)


def prepare():
    status = coverage()
    if status['complete']:
        print(f"Artwork ready: {status['cached']}/{status['total']} item and Ball images; "
              f"{len(status['references'])} reference images.", flush=True)
        return status
    print('Preparing complete item, Poke Ball, and reference artwork (first run needs internet)…', flush=True)
    try:
        if not (ART / 'source.json').exists():
            import_archive(fetch(SOURCE))
        fetch_missing()
    except Exception as exc:
        print(f'Could not finish artwork download: {exc}', flush=True)
    status = coverage()
    print(f"Artwork: {status['cached']}/{status['total']} cached; {len(status['references'])} references.", flush=True)
    if not status['complete']:
        print('Artwork is incomplete. Restart with internet to retry; missing IDs: ' +
              ', '.join(map(str, status['missing'])), flush=True)
    return status

if __name__ == '__main__':
    raise SystemExit(0 if prepare()['complete'] else 1)
