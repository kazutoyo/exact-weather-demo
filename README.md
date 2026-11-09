# reflex-exact-app

English | [日本語](README.ja.md)

The same weather app as [reflex-expo-app](https://github.com/kazutoyo/reflex-expo-app) (React Native / Expo) and [reflex-native-app-demo](https://github.com/kazutoyo/reflex-native-app-demo) (SwiftUI / Jetpack Compose), built with [Exact](https://github.com/expo/exact), Expo's new cross-platform runtime. One Contract view and one TypeScript data module run natively on iOS (UIKit), macOS (AppKit) and the web (DOM).

![iOS, macOS and web, driven in lockstep](docs/demo/three-platforms.gif)

- Three tabs: weather at the current location, favorites, and city search. API: [Open-Meteo](https://open-meteo.com/) (no API key)
- Location and reverse geocoding through `@exact/geolocation` and `@exact/geocoding`; favorites in a JSON file
- The look follows the SwiftUI version of the app

![SwiftUI (left) and Exact (right)](docs/native-vs-exact.png)

> [!NOTE]
> Exact is pre-1.0 and changes daily. This app was built against exact2 `94b8671` (November 2026).

## Files

| File | What it is |
|---|---|
| `app.contract` | The view: routes (three tabs, each with its own stack), state, actions and every screen |
| `app.ts` | The data module: Open-Meteo, favorites in `app:/data/favorites.json`, and the `grants` it may use |
| `app.test.contract` | Behavior tests; the same file passes on the web and in the iOS Simulator |
| `strings/en.json` | The location permission's purpose string |
| `tools/film.py`, `tools/compose.py` | Film the same flow on web, iOS and macOS with Exact's agent, then lay the three side by side |
| `tools/record-web.mjs` | Record the web build at 3x through Chrome DevTools Protocol |

## Run it

The app uses an Exact checkout at `../exact` by path.

```sh
git clone https://github.com/expo/exact ../exact
bun ../exact/scripts/exact.mjs setup   # once
bun install

bun exact.mjs web          # the dev loop at http://127.0.0.1:8765/
bun exact.mjs ios --run    # an iOS Simulator
bun exact.mjs mac --run    # this Mac
bun exact.mjs test web     # or: test ios
bun exact.mjs verify       # tests, light/dark, two widths, the largest text size
```

City search queries Open-Meteo by name in English (`Osaka`, `Tokyo`).
