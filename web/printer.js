'use strict';
// Browser port of printer.py + server.py's /api endpoints, used when no Python server answers (e.g. GitHub Pages).
// Keep in sync with printer.py; tests/printer_js_check.mjs compares both.
const MASK = (1n << 64n) - 1n, MIN_SEED = 946684800, MAX_SEED = 2871763199;
const rot = (x, n) => ((x << n) | (x >> (64n - n))) & MASK;

class RNG {
  constructor(seed) { this.a = BigInt(seed); this.b = 0x82A2B175229D6A5Bn; }
  next() {
    const a = this.a; let b = this.b;
    const result = (a + b) & MASK;
    b ^= a;
    this.a = rot(a, 24n) ^ b ^ ((b << 16n) & MASK);
    this.b = rot(b, 37n);
    return result;
  }
  integer(maximum) {
    const mask = (1n << BigInt(32 - Math.clz32(maximum - 1))) - 1n;  // Python bit_length
    for (;;) { const v = Number(this.next() & mask); if (v < maximum) return v; }
  }
}

function table(json, balls) {
  const entries = balls ? json.Table.flatMap(x => x.Param.Table) : json.Table.map(x => x.Param.Value);
  entries.sort((x, y) => x.EmergePercent - y.EmergePercent);
  const jump = [entries[0]];
  for (const e of entries) for (let i = 0; i < e.EmergePercent; i++) jump.push(e);
  if (jump.length !== 10001) throw Error('Invalid reward table.');
  return [entries, jump];
}

function makePrinter(itemsJson, ballsJson, NAMES) {
  const [ITEMS, ITEM_JUMP] = table(itemsJson, false), [BALLS, BALL_JUMP] = table(ballsJson, true);
  function printJob(rng, mode, count) {
    if (![0, 1, 2].includes(mode) || ![1, 5, 10].includes(count)) throw Error('Choose a valid mode and 1, 5, or 10 prints.');
    const rewards = []; let nextMode = 0;
    for (let i = 0; i < count; i++) {
      const bonus = rng.integer(1000) < 20;
      const entry = (mode === 2 ? BALL_JUMP : ITEM_JUMP)[rng.integer(10001)];
      const low = entry.LotteryItemNumMin, high = entry.LotteryItemNumMax;
      const amount = low === high ? low : low + rng.integer(high - low + 1);
      const id = entry.ItemId;
      rewards.push({id, name: NAMES[id] ?? `Item #${id}`, count: amount * (mode === 1 ? 2 : 1)});
      if (mode === 0 && bonus && nextMode === 0) nextMode = 1 + rng.integer(2);
    }
    return {rewards, nextMode};
  }
  function forecast(seed, mode, count, chain = []) {
    if (!(seed >= MIN_SEED && seed <= MAX_SEED)) throw Error('Choose a console date between 2000 and 2060.');
    const rng = new RNG(seed);
    for (const job of chain) { printJob(rng, Number(job.mode), Number(job.count)); rng.integer(100); }
    return printJob(rng, mode, count);
  }
  return {ITEMS, BALLS, forecast};
}

let localPrinter = null;
async function localApi(path, params) {
  if (!localPrinter) {
    const get = async url => (await fetch(url)).json();
    const [items, balls, names, references] = await Promise.all(['data/items.json', 'data/balls.json', 'data/names.json', 'art/references.json'].map(get));
    localPrinter = {...makePrinter(items, balls, names), names, references: references.map(r => ({...r, url: r.url.replace(/^\//, '')}))};
  }
  const {ITEMS, BALLS, forecast, names, references} = localPrinter;
  const now = Date.now(), local = now - new Date(now).getTimezoneOffset() * 60000;
  const clock = {unixMs: now, seed: Math.floor(local / 1000), local: new Date(local).toISOString().slice(0, 23)};
  const value = (key, fallback) => { const v = params[key] ?? fallback; if (!/^-?\d+$/.test(String(v))) throw Error(`Invalid ${key}.`); return Number(v); };
  if (path === 'status') return {...clock, urls: [location.href.split('#')[0]],
    artwork: {total: ITEMS.length + BALLS.length, cached: ITEMS.length + BALLS.length, missing: [], references, complete: true},
    items: [...ITEMS.map(x => [x, false]), ...BALLS.map(x => [x, true])].map(([x, ball]) => ({id: x.ItemId, name: names[x.ItemId], ball, chance: x.EmergePercent, min: x.LotteryItemNumMin, max: x.LotteryItemNumMax}))};
  const seed = value('seed', clock.seed), mode = value('mode', 0), count = value('count', 10);
  const chain = JSON.parse(params.chain ?? '[]');
  if (!Array.isArray(chain) || chain.length > 100) throw Error('A session can contain up to 100 jobs.');
  if (path === 'forecast') return {...clock, forecastSeed: seed, ...forecast(seed, mode, count, chain)};
  if (path !== 'search') throw Error('Unknown request.');
  const item = value('item', 0), bonus = value('bonus', 0), rank = value('rank', 0), window = value('window', 3600);
  if (!(window >= 60 && window <= 86400)) throw Error('Choose a time frame between 1 minute and 24 hours.');
  if (!item && bonus !== 1 && bonus !== 2) throw Error('Choose an item or a bonus to find.');
  if (rank && !item) throw Error('Choose a desired item to rank times by quantity.');
  if (bonus && mode !== 0) throw Error('Bonus activation can only be searched in Regular mode.');
  if (item && !(mode === 2 ? BALLS : ITEMS).some(x => x.ItemId === item)) throw Error('That item is unavailable in this mode.');
  let hits = [];
  for (let c = seed; c < Math.min(seed + window, MAX_SEED + 1); c++) {
    const result = forecast(c, mode, count);
    const total = result.rewards.reduce((s, x) => s + (x.id === item ? x.count : 0), 0);
    if ((!bonus || result.nextMode === bonus) && (!item || total)) {
      hits.push([total, c]);
      if (!rank && hits.length === 8) break;
    }
  }
  const matches = hits.length;
  if (rank) hits = hits.sort((x, y) => y[0] - x[0] || x[1] - y[1]).slice(0, 8);
  return {matches, results: hits.map(([total, s]) => ({seed: s, total, ...forecast(s, mode, count)}))};
}
if (typeof module !== 'undefined') module.exports = {makePrinter, localApi, RNG};
