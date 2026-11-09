// Records the web build driven by a scripted flow, at iPhone size and 3x, as JPEG frames
// plus a concat list for ffmpeg. Usage: bun tools/record-web.mjs <url> <outDir>
import { mkdirSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';

const [url = 'http://127.0.0.1:8790/', out = '.exact/rec/frames'] = process.argv.slice(2);
const CHROME = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9333;
mkdirSync(out, { recursive: true });

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${out}/../profile`,
  '--no-first-run', '--force-device-scale-factor=3', '--window-size=390,844', '--lang=ja-JP', '--hide-scrollbars', 'about:blank',
], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  target = await fetch(`http://127.0.0.1:${PORT}/json/list`).then((r) => r.json()).then((l) => l.find((t) => t.type === 'page')).catch(() => null);
}
const browserWs = (await fetch(`http://127.0.0.1:${PORT}/json/version`).then((r) => r.json())).webSocketDebuggerUrl;

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map(), listeners = [];
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } else listeners.forEach((f) => f(m));
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const n = ++id;
    waiting.set(n, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
    ws.send(JSON.stringify({ id: n, method, params }));
  });
  return new Promise((r) => (ws.onopen = () => r({ send, on: (f) => listeners.push(f), close: () => ws.close() })));
}

const browser = await connect(browserWs);
await browser.send('Browser.grantPermissions', { origin: new URL(url).origin, permissions: ['geolocation'] });
const page = await connect(target.webSocketDebuggerUrl);
await page.send('Page.enable');
await page.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
await page.send('Emulation.setTouchEmulationEnabled', { enabled: true });
await page.send('Emulation.setGeolocationOverride', { latitude: 35.6895, longitude: 139.6917, accuracy: 100 });
await page.send('Emulation.setLocaleOverride', { locale: 'ja-JP' });
await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });

// Frames arrive only when the page paints; each frame's duration is the gap to the next.
const frames = [];
page.on(async (m) => {
  if (m.method !== 'Page.screencastFrame') return;
  const { data, metadata, sessionId } = m.params;
  const file = `f${String(frames.length).padStart(5, '0')}.jpg`;
  writeFileSync(`${out}/${file}`, Buffer.from(data, 'base64'));
  frames.push({ file, t: metadata.timestamp });
  page.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
});
await page.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1170, maxHeight: 2532, everyNthFrame: 1 });
const loaded = new Promise((r) => page.on((m) => m.method === 'Page.loadEventFired' && r()));
await page.send('Page.navigate', { url });
await loaded;

// The flow, inside the page.
const flow = async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (id) => document.querySelector(`[data-testid="${id}"]`);
  const until = async (id) => { for (let i = 0; i < 150 && !$(id); i++) await sleep(100); if (!$(id)) throw new Error(`missing ${id}`); return $(id); };
  // Location is granted, so the app locates on its own.
  await until('temp-weather'); await sleep(3000);
  $('tab-search').click(); await sleep(900);
  const inp = $('search-input'); inp.focus();
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const ch of 'Osaka') { set.call(inp, inp.value + ch); inp.dispatchEvent(new InputEvent('input', { bubbles: true, data: ch, inputType: 'insertText' })); await sleep(200); }
  await sleep(400);
  inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
  await until('result-1853909'); await sleep(1600);
  $('result-1853909').click(); await until('place-search'); await sleep(2400);
  $('star-search').click(); await sleep(1300);
  $('tab-favorites').click(); await until('fav-temp-1853909'); await sleep(2000);
  $('fav-1853909').click(); await until('place-favorites'); await sleep(2200);
  history.back(); await sleep(1300);
  $('tab-weather').click(); await sleep(2500);
  return 'done';
};
await sleep(500);
const r = await page.send('Runtime.evaluate', { expression: `(${flow})()`, awaitPromise: true, returnByValue: true });
await page.send('Page.stopScreencast');
await sleep(300);
console.log('flow:', r.result?.value ?? r.exceptionDetails?.exception?.description);

const lines = frames.map((f, i) => `file '${f.file}'\nduration ${((frames[i + 1]?.t ?? f.t + 0.5) - f.t).toFixed(4)}`);
writeFileSync(`${out}/list.txt`, `${lines.join('\n')}\nfile '${frames.at(-1).file}'\n`);
console.log(`${frames.length} frames, ${(frames.at(-1).t - frames[0].t).toFixed(1)} s → ${out}/list.txt`);
page.close(); browser.close(); chrome.kill();
process.exit(0);
