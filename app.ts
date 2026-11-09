import type { Answer, Result, Sources, Storage } from './app.contract.d.ts';

// Open-Meteo (no API key). Favorites live in a JSON file.
const FORECAST = 'https://api.open-meteo.com';
const GEO = 'https://geocoding-api.open-meteo.com';
const FAVORITES = 'app:/data/favorites.json';
export const grants = [
  `net.fetch ${FORECAST}`,
  `net.fetch ${GEO}`,
  'device.geolocation-approximate locationPurpose',
  `fs.read ${FAVORITES}`,
  `fs.write ${FAVORITES}`,
].join('\n');

type Forecast = Result<'forecast'>;
type City = Result<'searchCities'>['items'][number];

const blank: Forecast = { ready: false, temp: 0, code: 0, days: [] };
async function get(url: string): Promise<any> {
  const res = await fetch(url, { exactTimeout: 10000 });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function forecast(lat: number, lon: number): Promise<Forecast> {
  const q = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: 'temperature_2m,weather_code',
    daily: 'weather_code,temperature_2m_max,temperature_2m_min',
    timezone: 'auto',
  });
  const r = await get(`${FORECAST}/v1/forecast?${q}`);
  return {
    ready: true,
    temp: r.current.temperature_2m,
    code: r.current.weather_code,
    days: r.daily.time.map((date: string, i: number) => ({
      date,
      code: r.daily.weather_code[i],
      max: r.daily.temperature_2m_max[i],
      min: r.daily.temperature_2m_min[i],
    })),
  };
}

function toCity(r: any): City {
  return {
    id: String(r.id),
    name: r.name,
    // admin1 and country can be the same (e.g. Singapore)
    region: [r.admin1, r.country].filter((s, i, a) => s && a.indexOf(s) === i).join(', '),
    lat: r.latitude,
    lon: r.longitude,
  };
}

async function searchCities(query: string): Promise<Result<'searchCities'>> {
  const name = query.trim();
  if (!name) return { query, items: [] };
  const q = new URLSearchParams({ name, count: '10', language: 'en' });
  const r = await get(`${GEO}/v1/search?${q}`);
  return { query, items: (r.results ?? []).map(toCity) }; // results is absent with 0 hits
}

// ponytail: unbounded in-memory city cache, fine for a session.
const cities = new Map<string, City>();
async function city(id: string): Promise<City> {
  const known = cities.get(id);
  if (known) return known;
  const c = toCity(await get(`${GEO}/v1/get?id=${encodeURIComponent(id)}&language=en`));
  cities.set(id, c);
  return c;
}

async function readFavorites(storage: Storage): Promise<City[]> {
  try {
    return JSON.parse(new TextDecoder().decode(await storage.fs.readFile(FAVORITES)));
  } catch {
    return []; // no file yet
  }
}

const sources: Sources = {
  // The weather tab: nothing until there is a position.
  forecast: ([lat, lon, located]) => (located ? forecast(lat, lon) : blank),

  searchCities: ([query]) => searchCities(query),

  // Every city opened on any tab's stack; one failed city doesn't fail the others.
  loadCities: async ([ids], _store, storage) => {
    const favs = new Set((await readFavorites(storage)).map((c) => c.id));
    return Promise.all(
      [...new Set(ids)].map(async (id) => {
        try {
          const c = await city(id);
          return { id, ok: true, city: c, forecast: await forecast(c.lat, c.lon), favorite: favs.has(id) };
        } catch {
          return { id, ok: false, city: { id, name: '', region: '', lat: 0, lon: 0 }, forecast: blank, favorite: false };
        }
      })
    );
  },

  // Favorites with each one's current weather (ready: false when it couldn't be fetched).
  loadFavorites: async (_args, _store, storage) =>
    Promise.all(
      (await readFavorites(storage)).map(async (c) => ({
        city: c,
        forecast: await forecast(c.lat, c.lon).catch(() => blank),
      }))
    ),

  toggleFavorite: async ([id, name, region, lat, lon], _store, storage) => {
    cities.set(id, { id, name, region, lat, lon });
    const all = await readFavorites(storage);
    const next = all.some((c) => c.id === id)
      ? all.filter((c) => c.id !== id)
      : [...all, { id, name, region, lat, lon }];
    await storage.fs.atomicWriteFile(FAVORITES, new TextEncoder().encode(JSON.stringify(next)));
    return { ok: true };
  },
};

export const answer: Answer = (source, args, store, storage, native) =>
  sources[source](args, store, storage, native);
