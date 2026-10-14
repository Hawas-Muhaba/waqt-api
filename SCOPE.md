# Waqt — System Scope, Architectural Boundaries & Engineering Limitations

This document defines the formal engineering boundaries, theological independence, and technical accuracy limits of the Waqt standard and software implementation.

---

## 1. Architectural Scope

Waqt implements the **Core Time Model v0.1**:

1. **Makkah Reference Anchor:** Global Hijri date assignments and reference lunar ephemerides are computed relative to the Makkah meridian (`lat=21.4225, lon=39.8262`).
2. **The Maghrib Day Boundary:** The Islamic civil day is defined mathematically as the continuous half-open interval:
   $$\text{Day}(L, D) = [M(L, D),\, M(L, D+1))$$
   where $M(L, D)$ is the local sunset (Maghrib) instant for day $D$.
3. **Continuous Hour Reading:** Time elapsed from the opening Maghrib is expressed in standard SI-minute hours. Days whose duration exceeds 86,400 SI seconds naturally read past `24:00:00` (e.g. `24:12:35`) without truncation.
4. **Invariant Event Positions:** All six solar/prayer events (Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha) are expressed as offsets from the opening Maghrib on the same continuous temporal axis.
5. **Pluggable Calendar Infrastructure:** Calendar resolution is decoupled from solar mechanics. Swapping a calendar provider alters only the reported Hijri date string, leaving astronomical instants and clock ticks byte-for-bit identical.
6. **Scheduling & Institutional Framework:** Scheduling intervals, windows, deadlines, and multi-term academic/fiscal calendars are built upon the Core Time Model without altering solar foundations.

---

## 2. Theological Scope & Technical Independence

### What Waqt Provides
Waqt is a **computational utility and software protocol**. It provides verifiable astronomical coordinates, deterministic time calculations, and standard interfaces for digital systems.

### What Waqt Does NOT Provide
- **Religious Rulings (Fatwas):** Waqt does not declare religious rulings, determine religious obligations, or mandate liturgical practices.
- **Authoritative Hilal Declarations:** Official declarations of the start of Ramadan, Eid al-Fitr, or Dhul Hijjah remain under the exclusive jurisdiction of recognized Islamic scholars, judicial councils, and national moon-sighting authorities.
- **Theological Bias:** The architecture is intentionally agnostic to theological disagreements. Pluggable providers allow any community, mosque, or government to deploy their accepted methodology (`umm-al-qura`, `local-observation`, `declared`, or `arithmetic-tabular`).

---

## 3. High-Latitude & Polar Boundary Handling

### The Undefined Horizon
In high-latitude and polar regions (such as northern Scandinavia, Alaska, or Antarctica during solstice periods), the sun may remain continuously above the horizon (midnight sun) or continuously below the horizon (polar night). Under these conditions, a physical sunset ($M$) does not occur.

### The Strict Non-Invention Policy
Waqt **never invents arbitrary times** or silently substitutes a simulated boundary:
- When a day boundary cannot be determined astronomically, Waqt returns `status: "UNDEFINED"`.
- The machine-readable reason returned is:
  > `"Maghrib (sunset) does not occur for this date/location — polar day or polar night. No high-latitude fallback is applied automatically; see SCOPE.md."`
- Individual prayer events that do not occur (e.g., Fajr depression angle not reached during white nights) explicitly return `instant: null` and `reading: null`.

### Guidance for Applications in Polar Regions
Consumers operating in high latitudes must explicitly apply their community's approved scholarly methodology (such as the *Aqrab al-Bilad* nearest-latitude rule, Makkah time estimation, or proportional seventh division) at the application or presentation layer.

---

## 4. Solar Engine & Measured Accuracy

### Computation Engine
The standard engine implements the NOAA solar calculation equations, augmented with:
- **Iterative Hour-Angle Solvers:** High-convergence iterative refinement for solar depression events.
- **Atmospheric Refraction:** Standard 34-arcminute atmospheric refraction model applied at the horizon.
- **Elevation Adjustment:** Geometric dip correction based on observer elevation (`elevation_m`), applied to sunrise and sunset:
  $$\text{dip} = \arccos\left(\frac{R}{R + h}\right)$$
- **Terrestrial Time (ΔT):** NASA polynomial model (`EspenakMeeusDeltaT`) wired into every solar calculation to bridge UTC wall time and Terrestrial Dynamical Time.

### Measured Accuracy Bands
Evaluated against the independent VSOP87 Level-A reference implementation across extensive geographic and temporal matrices:
- **Equatorial & Tropical Regions:** Agreement within **~1.0 second**.
- **Mid-Latitude Regions (up to 40°):** Agreement within **~1.0 to 2.5 seconds**.
- **High-Latitude Regions (>40°):** Agreement within **~3.5 to 5.0 seconds** (due to shallow solar horizon angles).

---

## 5. Calendar Providers & Honest Limitations

1. **`umm-al-qura` (Default):**
   - Implements the official astronomical criterion of the Umm al-Qura calendar of Saudi Arabia: conjunction occurring before sunset at Makkah, and the moon setting after sunset.
   - Evaluated across historical and future ranges (1700–2300 AH) with verified multi-year epoch anchors.
   - *Limitation:* Does not automatically incorporate Saudi Arabia's occasional manual sighting-based adjustments for Dhul-Hijjah or Ramadan without an explicit administrative override.

2. **`arithmetic-tabular`:**
   - Classical 30-year deterministic cycle (11 leap years per 30 years, epoch JDN 1948440).
   - Fully deterministic and offline, but typically varies from astronomical observation by 1 to 2 days.

3. **`declared` & `local-observation`:**
   - Enables administrative authorities or community observers to register verified dates and sighting locations while falling back to astronomical calculations outside the specified override dates.

---

## 6. Timezone & Civil Date Resolution

Local civil dates are resolved using standard IANA timezone lookups (`timezonefinder`), widening to a $\pm 3$-day bracket search around the target instant. This guarantees correct day association even across the International Date Line (such as Kiritimati, UTC+14), where civil time deviates significantly from solar time.

---

## 7. Versioning & Conformance

All behavioral guarantees, accuracy bands, and error envelopes are codified under **Conformance Contract 2.0.0** and protected by automated regression suites:
- Engine revision: `"2"` (Level-B certified, Level-A benchmarked)
- Conformance vector set: `2.0`
- Core time model specification: `waqt-core/0.1`
