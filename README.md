# Waqt (وقت) — Open Islamic Civil Time Standard & Software Engine

[![PyPI - waqt-core](https://img.shields.io/pypi/v/waqt-core?label=waqt-core&color=0ea5e9)](https://pypi.org/project/waqt-core/)
[![PyPI - waqt-local](https://img.shields.io/pypi/v/waqt-local?label=waqt-local&color=0ea5e9)](https://pypi.org/project/waqt-local/)
[![PyPI - waqt-api](https://img.shields.io/pypi/v/waqt-api?label=waqt-api&color=0ea5e9)](https://pypi.org/project/waqt-api/)
[![PyPI - waqt-client](https://img.shields.io/pypi/v/waqt-client?label=waqt-client&color=0ea5e9)](https://pypi.org/project/waqt-client/)
[![Conformance 2.0.0](https://img.shields.io/badge/conformance-2.0.0-emerald)](conformance/spec/CONFORMANCE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-amber.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

**Waqt** is an open-source civil time standard and computational infrastructure that models time according to Islamic astronomical tradition: **every day begins at local sunset (Maghrib)**.

Rather than forcing Islamic calendars and prayer times into arbitrary midnight-to-midnight solar grids, Waqt treats the day as a continuous, mathematically rigorous interval `[Maghrib(D), Maghrib(D+1))`. It provides deterministic temporal coordinates, pluggable Hijri calendar engines, high-accuracy solar mechanics, and scheduling algebra for modern applications.

---

## 🌟 Key Features

- **Maghrib-to-Maghrib Time Continuum:** Day boundaries are anchored to celestial physics: $[M_0, M_1)$. Exactly at sunset, the day rolls over and the clock resets to `00:00:00`.
- **Continuous 24h+ Clock:** Time advances in standard SI minutes from Maghrib. Extended solar days naturally read past `24:00:00` (e.g., `24:15:30`) without silent wraps or artificial clamping.
- **AT / BT 12-Hour Presentation:** Experimental human-friendly display mapping Before Twelve (`BT`, hours 00–11) and After Twelve (`AT`, hours 12–23) with explicit day-offset markers (`+1 day`).
- **Deterministic Solar Mechanics:** NOAA-based solar engine refined with iterative hour-angle solvers, atmospheric refraction, elevation modeling (`elevation_m`), and NASA polynomial ΔT corrections.
- **Calendar Interoperability:** Pluggable Hijri calendar system supporting official Umm al-Qura astronomical approximations, classical arithmetic tabular, and institutional declared overrides.
- **Cross-Platform Ecosystem:** Pure Python core engine, embeddable offline package, FastAPI HTTP server, CLI terminal utility, Python/JS SDKs, and static web frontend.
- **Formal Conformance:** Verified against Conformance Contract 2.0.0, 600+ portable test vectors, and an independent clean-room Node.js implementation.

---

## 📦 Package Architecture

The repository is organized into cleanly decoupled, independently versioned components:

```
waqt-api/
├── core/                         # waqt-core (PyPI: 0.7.0): pure calculation engine
│   └── waqt_core/                # Zero web dependencies (ephem, timezonefinder)
│       ├── core.py               # Core Time Model: [Maghrib(D), Maghrib(D+1))
│       ├── solar.py              # NOAA low-precision solar engine & solver
│       ├── hijri.py              # Hijri date protocol & arithmetic
│       ├── calendar_providers/   # Umm al-Qura, Arithmetic Tabular, Declared
│       ├── scheduling/           # Windows, deadlines, event-relative intervals
│       ├── institutional/        # Islamic week, fiscal year, academic year
│       └── display/at_bt/        # AT/BT 12-hour presentation formatter
├── local/                        # waqt-local (PyPI: 0.7.0): embeddable offline library
│   └── waqt_local/               # High-speed in-process API (no HTTP server required)
├── waqt/                         # waqt-api (PyPI: 0.6.0): FastAPI HTTP standard server
│   └── api/                      # 10+ endpoints with unified error & response envelopes
├── apps/
│   ├── cli/                      # waqt-cli (0.3.1): command-line terminal tool
│   ├── web/                      # waqt-web: responsive static website & live interactive dial
│   └── api-consumer/             # Zero-dependency standard-library HTTP consumer
├── sdks/
│   ├── python/                   # waqt-client (PyPI: 0.3.1): Python HTTP SDK
│   └── js/waqt-client/           # waqt-client (npm: 0.3.1): JavaScript/TypeScript SDK
├── conformance/                  # Conformance Contract 2.0.0, portable test vectors & JS runner
├── independent-astronomy/        # Level-B & Level-A (VSOP87) reference benchmarks
├── docs/                         # Specifications, guides, and architecture records
│   └── sprints/                  # Archived development sprint reports (Sprint 2 through 17)
└── tests/                        # Comprehensive test suite (unit, integration, vectors)
```

---

## 🚀 Quickstart

### 1. Install via PyPI

Choose the package that fits your use case:

```bash
# Pure computation engine (no web dependencies)
pip install waqt-core

# Embeddable offline library (full local API)
pip install waqt-local

# Python client SDK
pip install waqt-client

# Full HTTP server
pip install waqt-api
```

### 2. Using `waqt-local` (In-Process Python)

```python
from waqt_local import now, format_at_bt

# Compute current Waqt time for Makkah
res = now(lat=21.4225, lon=39.8262)

print(f"Hijri Date:    {res['hijri']['date']} ({res['hijri']['provider']})")
print(f"Waqt Reading:  {res['waqt']['reading']['display']}")
print(f"AT/BT Display: {format_at_bt(res['waqt']['reading']['display'])}")
print(f"Next Event:    {res['next_event']['name']} in {res['next_event']['countdown']['display']}")
```

### 3. Running from Source

```bash
# Clone the repository
git clone https://github.com/Hawas-Muhaba/waqt-api.git
cd waqt-api

# Install in development mode
pip install -r requirements.txt

# Start the API server
uvicorn waqt.api:app --reload --port 8000
```

Open `http://localhost:8000/docs` in your browser for the interactive Swagger documentation.

---

## 🌐 The HTTP API Contract

All responses conform to a unified envelope `{ meta, data, error }`.

### Core Time & Calendar Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/waqt` | `GET` | Full snapshot: day boundaries, clock reading, 6 events, Hijri date, timezone |
| `/v1/day` | `GET` | Day interval only: opening/closing Maghrib instants and day duration |
| `/v1/events` | `GET` | All 6 prayer/solar events (Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha) |
| `/v1/hijri` | `GET` | Authoritative Hijri date resolution for a given civil date |
| `/v1/calendar` | `GET` | Discovery catalog of available calendar providers |
| `/v1/conversions`| `GET` | Pure calendar conversion between Gregorian and Hijri |
| `/v1/location` | `GET` | IANA timezone and local civil date resolution |
| `/v1/version` | `GET` | Machine-readable engine revision, accuracy level, and version axes |

### Scheduling Engine

| Endpoint | Method | Description |
|---|---|---|
| `/v1/schedule/snapshot` | `GET` | Current point in day, active interval, elapsed/remaining time |
| `/v1/schedule/span` | `GET` | Analyzes whether an interval `[start, end)` crosses a Maghrib boundary |
| `/v1/schedule/resolve` | `POST` | Evaluates complex scheduling rules (windows, deadlines, offsets) |

### Institutional Calendars

| Endpoint | Method | Description |
|---|---|---|
| `/v1/institutional/week` | `GET` | Islamic week containing an instant (Friday slot, configurable start) |
| `/v1/institutional/fiscal-year` | `GET`/`POST` | Configurable Islamic fiscal year resolution |
| `/v1/institutional/academic-year` | `GET`/`POST`| Configurable academic terms and holiday calendars |

---

## 🧪 Testing & Verification

Run the entire automated verification suite across all layers:

```bash
# Run core and API pytest suite
pytest tests/ -v

# Run reference CLI tests
pytest apps/cli/tests/test_cli.py -v

# Run web app structural conformance tests
pytest apps/web/tests/test_site_structure.py -v

# Run web frontend JavaScript unit tests (Node.js required)
node --test apps/web/tests/js/site.test.mjs
```

---

## 🤝 Contributing

We warmly welcome developers, astronomers, designers, and students of Islamic jurisprudence to join the Waqt project.

- **Contribution Guide:** Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for environment setup and PR guidelines.
- **Scope & Limitations:** Review [`SCOPE.md`](SCOPE.md) for architectural boundaries and technical honesty.
- **Specifications:** Dive into [`docs/`](docs/) for in-depth time-model, astronomy, and calendar documentation.
- **Questions & Ideas:** Reach out to the maintainers at [`waqtapi@gmail.com`](mailto:waqtapi@gmail.com) or open an issue on GitHub.

---

## ☕ Support the Project

Waqt is an open community infrastructure project. Our public demonstration server is currently deployed on free-tier cloud hosting that will expire soon. 

If you would like to help cover ongoing server hosting expenses and support the team in building further open-source technology for the Ummah and humanity, you can support us on Ko-fi:

👉 **[Support Waqt on Ko-fi](https://ko-fi.com/ummatidawah)** *(Entirely optional, deeply appreciated)*

---

## 📜 Governance & License

- **Logical / Idea Owner:** Dr. Salim Muhammed Redi
- **Technical Maintainer:** Hawas Muhaba Hussein
- **License:** [MIT License](LICENSE) — free and open for personal, academic, and commercial integration.
