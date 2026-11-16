"""ItemPrinterDeGacha calculation port. GPL-3.0; see THIRD_PARTY.md."""
import json
from pathlib import Path

DATA = Path(__file__).parent / 'web' / 'data'
MASK = (1 << 64) - 1
MIN_SEED, MAX_SEED = 946684800, 2871763199
MODES = ('Regular', 'Item bonus', 'Ball bonus')
NAMES = json.loads((DATA / 'names.json').read_text(encoding='utf-8'))

class RNG:
    def __init__(self, seed):
        self.a, self.b = seed, 0x82A2B175229D6A5B

    def next(self):
        a, b = self.a, self.b
        result = (a + b) & MASK
        b ^= a
        self.a = (((a << 24) | (a >> 40)) ^ b ^ (b << 16)) & MASK
        self.b = ((b << 37) | (b >> 27)) & MASK
        return result

    def integer(self, maximum):
        mask = (1 << (maximum - 1).bit_length()) - 1
        while True:
            value = self.next() & mask
            if value < maximum:
                return value


def table(filename, balls=False):
    root = json.loads((DATA / filename).read_text())['Table']
    entries = [v for x in root for v in x['Param']['Table']] if balls else [x['Param']['Value'] for x in root]
    entries.sort(key=lambda v: v['EmergePercent'])
    assert sum(x['EmergePercent'] for x in entries) == 10000
    jump = [entries[0]]
    for entry in entries:
        jump.extend([entry] * entry['EmergePercent'])
    return entries, jump

ITEMS, ITEM_JUMP = table('items.json')
BALLS, BALL_JUMP = table('balls.json', True)


def print_job(rng, mode, count):
    if mode not in (0, 1, 2) or count not in (1, 5, 10):
        raise ValueError('Choose a valid mode and 1, 5, or 10 prints.')
    rewards, next_mode = [], 0
    for _ in range(count):
        bonus = rng.integer(1000) < 20
        entry = (BALL_JUMP if mode == 2 else ITEM_JUMP)[rng.integer(10001)]
        low, high = entry['LotteryItemNumMin'], entry['LotteryItemNumMax']
        amount = low if low == high else low + rng.integer(high - low + 1)
        item_id = entry['ItemId']
        rewards.append({'id': item_id, 'name': NAMES.get(str(item_id), f'Item #{item_id}'), 'count': amount * (2 if mode == 1 else 1)})
        if mode == 0 and bonus and next_mode == 0:
            next_mode = 1 + rng.integer(2)
    return {'rewards': rewards, 'nextMode': next_mode}


def forecast(seed, mode, count, chain=()):
    if not MIN_SEED <= seed <= MAX_SEED:
        raise ValueError('Choose a console date between 2000 and 2060.')
    rng = RNG(seed)
    for job in chain:
        print_job(rng, int(job['mode']), int(job['count']))
        rng.integer(100)  # The game consumes an animation roll between jobs.
    return print_job(rng, mode, count)
