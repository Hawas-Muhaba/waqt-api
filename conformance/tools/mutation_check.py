#!/usr/bin/env python3
"""Mutation check of the conformance suite itself: each mutation breaks ONE semantic rule of the independent
implementation; the suite must report at least one normative failure for it.  Writes reports/mutation-check.md."""
import json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUT = [
 ("day interval closed at the opening Maghrib (<= becomes <)", "src/waqtday.mjs", "if (m !== null && m <= us) { j = k; break; }", "if (m !== null && m < us) { j = k; break; }", "DAY-002"),
 ("label = transit date instead of civil date of the closing Maghrib instant", "src/waqtday.mjs", "label_day: localDateNum(this.zone, close), open,", "label_day: k, open,", "DAY-004"),
 ("label date taken in UTC instead of the location's IANA zone", "src/waqtday.mjs", "label_day: localDateNum(this.zone, close), open,", "label_day: Math.floor(close / 86400e6), open,", "DAY-007"),
 ("elevation dip ignored", "src/astro/events.mjs", "export const dipDeg = (elev) => (elev > 0 ? (1.76 / 60) * Math.sqrt(elev) : 0);", "export const dipDeg = (elev) => 0;", "EVT-006"),
 ("Isha angle used for Fajr", "src/astro/events.mjs", "morning('fajr', -profile.fajr_angle_deg, 'Fajr');", "morning('fajr', -profile.isha_angle_deg, 'Fajr');", "EVT-005"),
 ("Asr shadow ratio ignored", "src/astro/events.mjs", "Math.atan(1 / (profile.asr_shadow_ratio + Math.tan(zen)))", "Math.atan(1 / (1 + Math.tan(zen)))", "EVT-001"),
 ("tabular epoch off by one day", "src/calendar/tabular.mjs", "export const HIJRI_EPOCH_JDN = 1948440;", "export const HIJRI_EPOCH_JDN = 1948441;", "CAL-001"),
 ("stale-if-error disabled", "src/calendar/providers.mjs", "if (stale && now - stale.at < cfg.max_stale_seconds)", "if (false)", "PRV-004"),
 ("circuit breaker never opens", "src/calendar/providers.mjs", "if (now < openUntil) failure = 'circuit-open';", "if (false) failure = 'circuit-open';", "PRV-005"),
 ("Retry-After not capped", "src/calendar/providers.mjs", "Math.min(retry, cfg.max_retry_after_seconds)", "retry", "PRV-005"),
 ("override fires on every date", "src/calendar/providers.mjs", "if (parseDate(p.override_date) !== day) return null;", "", "CAL-008"),
 ("polar day guessed (undefined Maghrib replaced by transit+6h)", "src/astro/events.mjs", "    out.events[name] = t;\n    if (t === null) out.reasons[name] = noonAlt < target\n      ? `${label}: the Sun never reaches ${target.toFixed(4)} deg on this date (polar night)`\n      : `${label}: the Sun never falls to ${target.toFixed(4)} deg on this date (polar day / white night)`;\n  };\n\n  morning('fajr'", "    out.events[name] = t === null ? T + 6 * H : t;\n  };\n\n  morning('fajr'", "UND-001"),
 ("scheduling: window end treated as inclusive by default", "src/schedule.mjs", "end_inclusive: iv.end_inclusive ?? false", "end_inclusive: iv.end_inclusive ?? true", "SCH-002"),
 ("fixed 86400 s day length reported", "src/waqtday.mjs", "length_seconds: len }", "length_seconds: 86400 }", "DAY-006"),
]
def run(adapter_dir):
    cmd = ["python3", os.path.join(ROOT, "harness", "waqt_conform.py"), "--adapter", f"node {adapter_dir}/src/cli.mjs", "--label", "mut",
           "--out", tempfile.mkdtemp(), "--name", "m", "--suite", "day-model", "--suite", "metamorphic", "--suite", "calendar-core", "--suite", "calendar-providers",
           "--suite", "provider-failure", "--suite", "legacy-scheduling", "--suite", "gregorian-time", "--suite", "scheduling-defaults"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=900)
    m = re.search(r"normative pass=(\d+) fail=(\d+)", p.stderr)
    out = os.path.join(cmd[cmd.index("--out") + 1], "m.json")
    d = json.load(open(out))["runs"][0]
    reqs = sorted({r for v in d["vectors"] if v["verdict"] == "FAIL" and v["tier"] in ("exact", "tolerance") for r in v["requirements"]} |
                  {r for v in d["metamorphic"] if v["verdict"] == "FAIL" for r in v["requirements"]})
    return int(m.group(2)), reqs
rows = []
for name, f, old, new, expect in MUT:
    tmp = tempfile.mkdtemp(); d = os.path.join(tmp, "independent"); shutil.copytree(os.path.join(ROOT, "independent"), d, ignore=shutil.ignore_patterns("node_modules"))
    s = open(os.path.join(d, f)).read()
    if old not in s:
        rows.append((name, expect, "MUTATION NOT APPLICABLE (pattern missing)", [])); continue
    open(os.path.join(d, f), "w").write(s.replace(old, new, 1))
    n, reqs = run(d)
    rows.append((name, expect, "CAUGHT" if n and expect in reqs else ("caught, different requirement" if n else "SURVIVED"), [n, reqs]))
    print(rows[-1][:3], rows[-1][3][:1], file=sys.stderr)
L = ["# Mutation check of the conformance suite\n", "Each row breaks one rule in a copy of the independent implementation and re-runs the relevant suites.\n",
     "| mutation | expected to violate | outcome | failing normative vectors | requirements reported failing |", "|---|---|---|---|---|"]
for name, expect, out, extra in rows:
    L.append(f"| {name} | {expect} | **{out}** | {extra[0] if extra else '-'} | {', '.join(extra[1][:8]) if extra else '-'} |")
open(os.path.join(ROOT, "reports", "mutation-check.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
