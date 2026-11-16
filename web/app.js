'use strict';
const $ = id => document.getElementById(id);
const modes = ['Regular', 'Item bonus', 'Ball bonus'];
let baseSeed = 0, basePc = 0, syncedAt = 0, lastSync = 0, items = [], urls = [];
let target = null, shownSeed = null, shownMode = 0, shownCount = 10, session = null;
let pending = false, generation = 0, lastRendered = '', syncBusy = false;
let artStatus = null, libraryKey = "";
function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
function read(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
const dateFor = seed => new Date(seed * 1000).toISOString().slice(0,19);
const displayDate = seed => dateFor(seed).replace('T', ' ');
const timeFor = seed => dateFor(seed).slice(11);
const waitText = s => s < 0 ? 'passed' : s >= 3600 ? `in ${Math.floor(s / 3600)}h ${Math.floor(s % 3600 / 60)}m` : s >= 60 ? `in ${Math.floor(s / 60)}m ${s % 60}s` : `in ${s}s`;
const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
function offset() { const n = Number($('offset').value); if (!$('offset').checkValidity() || !Number.isInteger(n)) throw Error('Enter a whole number of seconds for the console offset.'); return n; }
function current() { return baseSeed + Math.floor((basePc + performance.now() - syncedAt) / 1000) - Math.floor(basePc / 1000); }
function tracked() { return current() + offset(); }
function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
let serverless = null;  // decided on first call: no Python server (e.g. GitHub Pages) → calculate in the browser
async function api(path, params = {}) {
  if (serverless === null) serverless = await fetch('api/status', {cache:'no-store'}).then(r => !r.headers.get('content-type')?.includes('json'), () => true);
  if (serverless) return localApi(path, params);
  const response = await fetch('api/' + path + '?' + new URLSearchParams(params), {cache:'no-store'}); const data = await response.json(); if (!response.ok) throw Error(data.error || 'The server could not complete this request.'); return data; }
function renderItems() {
  const previous = $('item').value;
  $('item').replaceChildren(new Option('Any item', '0'));
  items.filter(x => x.ball === ($('mode').value === '2')).sort((a,b) => a.name.localeCompare(b.name)).forEach(x => $('item').add(new Option(x.name, x.id)));
  if ([...$('item').options].some(x => x.value === previous)) $('item').value = previous;
  $('findBonus').disabled = $('mode').value !== '0';
  if ($('findBonus').disabled) $('findBonus').value = '0';
  updateSelectedItem();
}
async function sync(initial = false) {
  if (syncBusy) return; syncBusy = true;
  try {
    const start = performance.now(), data = await api('status');
    const midpoint = (start + performance.now()) / 2;
    baseSeed = data.seed; basePc = Date.parse(data.local + 'Z'); syncedAt = midpoint; lastSync = performance.now();
    items = data.items; urls = data.urls;
    artStatus = data.artwork; renderArtworkStatus(); renderLibrary();
    $('connection').textContent = '● PC clock synced';
    if (initial) { renderItems(); $('target').value = dateFor(tracked() + 60); }
  } catch (e) { $('connection').textContent = '● Disconnected'; error('Cannot reach the PC. Keep the server running and reconnect to the same Wi-Fi.'); }
  finally { syncBusy = false; }
}
function invalidate() { generation++; lastRendered = ''; }
function setTarget(seed) {
  if (session) endSession();
  target = seed; $('live').checked = false; $('target').value = dateFor(seed); invalidate(); tick();
}
let renderToken = 0;
async function renderForecast(data, seed, mode, count) {
  const token = ++renderToken;
  const rows = data.rewards.map((item, index) => {
    const row = document.createElement('li');
    row.classList.toggle('wanted', String(item.id) === $('item').value);
    for (const [cls, text] of [['number', String(index+1).padStart(2,'0')], ['', item.name]]) {
      const span = document.createElement('span'); span.className = cls; span.textContent = text; row.append(span);
    }
    const artButton = document.createElement('button'); artButton.className = 'reward-art'; artButton.setAttribute('aria-label', 'View artwork: ' + item.name); artButton.append(itemImage(item)); artButton.onclick = () => openArtwork(item); row.insertBefore(artButton, row.children[1]);
    const quantity = document.createElement('strong'); quantity.textContent = '×' + item.count; row.append(quantity); return row;
  });
  // Swap rows in only once their images are decoded, so they don't blink blank each second.
  await Promise.all(rows.flatMap(row => [...row.querySelectorAll('img')].map(img => img.decode().catch(() => {}))));
  if (token !== renderToken) return;
  shownSeed = seed; shownMode = mode; shownCount = count;
  $('forecastTime').textContent = `${displayDate(seed)} · ${count} prints · ${modes[mode]}`;
  $('forecastState').textContent = session ? 'Session' : $('live').checked ? 'Live' : 'Target';
  $('rewards').replaceChildren(...rows);
  $('bonus').textContent = data.nextMode ? modes[data.nextMode] : 'None';
}
async function refresh() {
  if (!baseSeed || pending) return;
  let seed;
  try { seed = session ? session.seed : $('live').checked ? tracked() : target; } catch(e) { error(e.message); return; }
  if (seed === null) return;
  const mode = Number($('mode').value), count = Number($('count').value);
  const key = JSON.stringify([seed,mode,count,session?.chain]);
  if (key === lastRendered) return;
  const version = generation; pending = true;
  try {
    const data = await api('forecast', {seed,mode,count,chain:JSON.stringify(session?.chain || [])});
    if (version !== generation) return;
    await renderForecast(data,seed,mode,count); lastRendered = key; error();
  } catch(e) { error(e.message); }
  finally { pending = false; }
}
function tick() {
  if (!baseSeed) return;
  try {
    const now = current(), consoleNow = tracked();
    $('clock').textContent = timeFor(now); $('date').textContent = displayDate(now).slice(0,10) + ' · Computer local time';
    $('consoleClock').textContent = timeFor(consoleNow); $('seed').textContent = consoleNow;
    if (target !== null) {
      const diff = target - consoleNow;
      $('countdown').textContent = diff === 0 ? 'Target second — now' : `${diff < 0 ? '+' : '−'}${Math.abs(diff)} s`;
      $('countdown').classList.toggle('urgent', diff >= 0 && diff <= 10);
      $('targetHint').textContent = diff < 0 ? 'Target has passed. Choose another time or return to live.' : displayDate(target);
    }
    document.querySelectorAll('.wait').forEach(node => { node.textContent = `${waitText(node.dataset.seed - consoleNow)} · ${displayDate(node.dataset.seed).slice(0, 10)}`; });
    if (performance.now() - lastSync > 15000) { $('connection').textContent = '● Reconnecting…'; sync(); }
    refresh();
  } catch(e) { error(e.message); }
}
$('mode').onchange = () => { renderItems(); invalidate(); save('printerMode', $('mode').value); tick(); };
$('count').onchange = () => { invalidate(); save('printerCount', $('count').value); tick(); };
$('offset').oninput = () => { invalidate(); try { save('printerOffset',offset()); tick(); } catch(e) { error(e.message); } };
$('preview').onclick = () => {
  if (!$('target').value || !$('target').checkValidity()) return error('Choose a valid target date between 2000 and 2060.');
  setTarget(Math.floor(Date.parse($('target').value + 'Z') / 1000));
};
function goLive() { endSession(); target = null; $('live').checked = true; $('countdown').textContent = 'Choose a target'; $('targetHint').textContent = 'Preview a time or pick a search result.'; invalidate(); tick(); }
$('now').onclick = goLive;
$('live').onchange = () => { if ($('live').checked) goLive(); else if (shownSeed !== null) setTarget(shownSeed); };
function endSession() { session = null; $('session').hidden = true; $('startSession').hidden = false; $('live').disabled = false; invalidate(); }
$('startSession').onclick = () => {
  if (shownSeed === null || pending || $('error').hidden === false) return error('Wait for a valid forecast before starting a session.');
  session = {seed:shownSeed,chain:[]}; target = shownSeed; $('target').value = dateFor(target); $('live').checked = false; $('live').disabled = true;
  $('session').hidden = false; $('startSession').hidden = true; $('sessionInfo').textContent = 'Session job 1 · starting from the displayed seed'; invalidate(); tick();
};
$('nextJob').onclick = () => {
  if (pending || !session || !lastRendered) return;
  if (session.chain.length >= 100) return error('Session limit reached. End this session and re-enter the printer to begin another.');
  session.chain.push({mode:shownMode,count:shownCount}); $('sessionInfo').textContent = `Session job ${session.chain.length + 1} · continuing without reseeding`; invalidate(); tick();
};
$('endSession').onclick = goLive;
function matchButton(result, index, wanted, wantedName, mode, count) {
  const button = el('button', 'match'); button.type = 'button';
  const body = el('span'), head = el('span', 'match-head');
  const wait = el('small', 'wait', `${waitText(result.seed - tracked())} · ${displayDate(result.seed).slice(0, 10)}`); wait.dataset.seed = result.seed;
  head.append(el('span', 'match-rank', '#' + (index + 1)), el('span', 'match-time', timeFor(result.seed)), wait);
  const strip = el('span', 'match-art');
  result.rewards.forEach(item => { const image = itemImage(item); image.classList.toggle('wanted', item.id === wanted); strip.append(image); });
  body.append(head, strip, el('small', 'match-detail', result.rewards.map(x => `${x.name} ×${x.count}`).join(' · ')));
  const side = el('span', 'match-total');
  if (wanted) side.append(el('strong', '', '×' + result.total), el('small', '', wantedName));
  else side.append(el('small', '', result.nextMode ? modes[result.nextMode] + ' next' : ''));
  side.append(el('span', 'match-go', 'Track →'));
  button.append(body, side);
  button.onclick = () => { $('mode').value = mode; $('count').value = count; renderItems(); setTarget(result.seed); $('countdown').scrollIntoView({block:'center',behavior:'smooth'}); };
  return button;
}
$('searchForm').onsubmit = async event => {
  event.preventDefault(); $('searchButton').disabled = true; $('searchButton').textContent = 'Searching…'; $('matches').setAttribute('aria-busy', 'true');
  const summary = el('p', 'match-summary');
  try {
    const mode = Number($('mode').value), count = Number($('count').value), rank = $('rankBy').value === '1';
    const wanted = Number($('item').value), wantedName = $('item').selectedOptions[0].text;
    const span = 'in the ' + $('searchWindow').selectedOptions[0].text.toLowerCase();
    const data = await api('search', {seed: tracked() + 2, mode, count, item: wanted, bonus: $('findBonus').value, rank: Number(rank), window: $('searchWindow').value});
    summary.textContent = !data.results.length ? `No matching times ${span}. Try a longer time frame, 10 prints, or a different item or bonus.`
      : rank ? `Most ${wantedName} ${span} (${count} prints, ${modes[mode]}): top ${data.results.length} of ${data.matches} matching seconds.`
      : `Soonest ${data.results.length} matching times ${span}.`;
    $('matches').replaceChildren(summary, ...data.results.map((result, index) => matchButton(result, index, wanted, wantedName, mode, count)));
  } catch(e) {
    summary.className += ' bad'; summary.textContent = e.message; $('matches').replaceChildren(summary);
  } finally { $('searchButton').disabled = false; $('searchButton').textContent = 'Find times'; $('matches').removeAttribute('aria-busy'); }
};
$('phoneButton').onclick = () => {
  $('phoneUrls').replaceChildren();
  (urls.length ? urls : [location.origin]).forEach(url => { const link = document.createElement('a'); link.href = url; link.textContent = url; $('phoneUrls').append(link); });
  $('phoneDialog').showModal();
};
$('closePhone').onclick = () => $('phoneDialog').close();
document.addEventListener('visibilitychange', () => { if (!document.hidden) { invalidate(); sync().then(tick); } });
$('offset').value = read('printerOffset',0);
$('mode').value = ['0','1','2'].includes(read('printerMode','0')) ? read('printerMode','0') : '0';
$('count').value = ['1','5','10'].includes(read('printerCount','10')) ? read('printerCount','10') : '10';
setupArtwork();
sync(true).then(tick); setInterval(tick,100);

function itemImage(item, lazy = false) {
  const image = document.createElement('img');
  image.src = 'art/items/' + item.id + '.png'; image.alt = item.name; image.width = 48; image.height = 48;
  image.decoding = 'async'; if (lazy) image.loading = 'lazy';
  image.onerror = () => { image.classList.add('missing-art'); image.alt = 'Image unavailable: ' + item.name; };
  return image;
}
function renderArtworkStatus() {
  const notice = $('artworkNotice');
  notice.hidden = Boolean(artStatus?.complete);
  notice.textContent = artStatus?.complete ? '' : `Artwork download incomplete: ${artStatus?.cached ?? 0}/${artStatus?.total ?? 156} reward images available. Restart the server with internet to download all missing artwork.`;
  $('artworkCount').textContent = `${artStatus?.cached ?? 0}/${items.length} images`;
}
function updateSelectedItem() {
  const image = $('selectedItemImage'), item = items.find(x => String(x.id) === $('item').value);
  image.hidden = !item; if (item) { image.src = 'art/items/' + item.id + '.png'; image.alt = item.name; }
}
function renderLibrary(force = false) {
  const filter = $('artFilter').value, query = $('artSearch').value.trim().toLowerCase();
  const key = JSON.stringify([filter,query,items,artStatus?.cached]);
  if (!force && libraryKey === key) return; libraryKey = key;
  const selected = items.filter(x => (filter === 'all' || x.ball === (filter === 'balls')) &&
    (x.name.toLowerCase().includes(query) || String(x.id).includes(query)));
  $('artGrid').replaceChildren(...selected.sort((a,b) => a.ball === b.ball ? a.name.localeCompare(b.name) : Number(b.ball)-Number(a.ball)).map(item => {
    const button = document.createElement('button'); button.className = 'art-tile';
    button.append(itemImage(item,true));
    const label = document.createElement('span'); label.textContent = item.name; button.append(label);
    button.onclick = () => openArtwork(item); return button;
  }));
  if (!selected.length) $('artGrid').textContent = 'No matching items.';
  $('referenceCount').textContent = `(${artStatus?.references?.length ?? 0})`;
}
function openArtwork(item) {
  $('largeArt').src = 'art/items/' + item.id + '.png'; $('largeArt').alt = item.name;
  $('artName').textContent = item.name; $('artInfo').textContent = `Item #${item.id} · ${item.ball || items.find(x => x.id === item.id)?.ball ? 'Ball bonus mode' : 'Regular / Item bonus mode'}`;
  $('artOriginal').href = 'art/items/' + item.id + '.png'; $('searchForArt').hidden = false;
  $('searchForArt').onclick = () => {
    const ball = items.find(x => x.id === item.id)?.ball;
    $('mode').value = ball ? '2' : '0'; renderItems(); $('item').value = String(item.id); updateSelectedItem();
    $('findBonus').value = '0'; invalidate(); tick(); $('artDialog').close(); $('searchForm').scrollIntoView({block:'center'});
  };
  $('artDialog').showModal();
}
function setupArtwork() {
  $('item').addEventListener('change', () => { updateSelectedItem(); invalidate(); tick(); });  // re-highlight the wanted item in the forecast
  $('artSearch').oninput = () => renderLibrary(); $('artFilter').onchange = () => renderLibrary();
  $('closeArt').onclick = () => $('artDialog').close();
  document.querySelector('.reference-details').addEventListener('toggle', event => {
    if (!event.target.open) return;
    $('referenceGrid').replaceChildren(...(artStatus?.references || []).map(ref => {
      const button = document.createElement('button'); button.className = 'art-tile';
      const image = document.createElement('img'); image.src = ref.url; image.alt = ref.name; image.loading = 'lazy';
      const label = document.createElement('span'); label.textContent = ref.name.split('/').pop(); button.append(image,label);
      button.onclick = () => { $('largeArt').src = ref.url; $('largeArt').alt = ref.name; $('artName').textContent = label.textContent; $('artInfo').textContent = ref.name; $('artOriginal').href = ref.url; $('searchForArt').hidden = true; $('artDialog').showModal(); };
      return button;
    }));
  });
}
