// providers.mjs -- calendar provider dispatch: tabular, umm-al-qura, declared, local-observation,
// and a behavioural MODEL of the remote 'aladhan' provider (no network is ever touched).
import { WaqtError, parseDate, formatDate, daysFromCivil } from '../timeutil.mjs';
import * as T from './tabular.mjs';
import * as U from './ummalqura.mjs';

export const PROVIDERS = ['arithmetic-tabular', 'umm-al-qura', 'declared', 'local-observation', 'aladhan'];
const fmtH = (y, m, d) => `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

function result(h, extra = {}) {
  return {
    year: h.year, month: h.month, day: h.day, date: fmtH(h.year, h.month, h.day),
    month_name: T.MONTH_NAMES[h.month - 1],
    display: `${h.day} ${T.MONTH_NAMES[h.month - 1]} ${h.year} AH`,
    provider: h.provider, source: 'local', fallback_reason: null, ...extra,
  };
}
const local = (provider, h) => ({ ...h, provider });

function fromTabular(day) { return local('arithmetic-tabular', T.tabularFromDay(day)); }
function fromUaq(day) { return local('umm-al-qura', U.uaqFromDay(day)); }

function overrideHit(day, p, key) {
  if (!p || p.override_date == null) return null;
  if (parseDate(p.override_date) !== day) return null;
  const v = p[key];
  if (!v) return null;
  T.validateHijri(v.year, v.month, v.day);
  return v;
}

export function hijriFromDay(day, provider = 'umm-al-qura', params = {}) {
  switch (provider) {
    case 'arithmetic-tabular': return result(fromTabular(day));
    case 'umm-al-qura': return result(fromUaq(day));
    case 'declared': {
      const v = overrideHit(day, params, 'declared');
      return v ? result(local('declared', v)) : result(fromTabular(day));
    }
    case 'local-observation': {
      const v = overrideHit(day, params, 'sighting');
      if (!v) return result(fromTabular(day));
      return result(local('local-observation', v), { source_note: params.observed_at ? `reported sighting; observed at ${JSON.stringify(params.observed_at)}` : 'reported sighting' });
    }
    case 'aladhan': return aladhanScenario({ steps: [{ at_seconds: 0, date: formatDate(day), remote: params.remote || { kind: 'unreachable' } }], config: params.config || {} })[0];
    default: throw new WaqtError('UNKNOWN_CALENDAR_PROVIDER', `unknown calendar provider: ${provider}`);
  }
}

export function hijriToDay(y, m, d, provider = 'umm-al-qura') {
  switch (provider) {
    case 'arithmetic-tabular': T.validateHijri(y, m, d, T.tabularMonthLength(y, m)); return T.tabularToDay(y, m, d);
    case 'umm-al-qura': T.validateHijri(y, m, d); return U.uaqToDay(y, m, d);
    case 'declared': case 'local-observation': case 'aladhan':
      throw new WaqtError('UNSUPPORTED_OPERATION', `provider ${provider} does not support reverse conversion`);
    default: throw new WaqtError('UNKNOWN_CALENDAR_PROVIDER', `unknown calendar provider: ${provider}`);
  }
}

export function monthLength(y, m, provider = 'umm-al-qura') {
  if (!Number.isInteger(y) || !Number.isInteger(m) || y < 1 || m < 1 || m > 12) throw new WaqtError('INVALID_HIJRI_DATE', `no such Hijri month: ${y}-${m}`);
  if (provider === 'arithmetic-tabular') return T.tabularMonthLength(y, m);
  if (provider === 'umm-al-qura') return U.uaqMonthLength(y, m);
  throw new WaqtError('UNSUPPORTED_OPERATION', `provider ${provider} does not support month enumeration`);
}

// ---- AlAdhan behavioural model ----------------------------------------------------------------
// Implements the rules written in docs/LIVE-INTEGRATIONS.md, driven by a SCRIPTED remote:
//   remote.kind: ok{hijri}, timeout, network-error, http{status,retry_after?}, malformed,
//                echo-mismatch{hijri}, oversize, unreachable(=network-error)
const WINDOW_MIN = daysFromCivil(1900, 1, 1), WINDOW_MAX = daysFromCivil(2076, 12, 31);
export function aladhanScenario(sc) {
  const cfg = { enabled: true, ttl_seconds: 12 * 3600, max_stale_seconds: 7 * 86400, cooldown_seconds: 30, max_retry_after_seconds: 600, max_plausible_delta_days: 3, requests_per_minute: 30, soft_failure_limit: 3, ...(sc.config || {}) };
  const cache = new Map();           // day -> {hijri, at}
  let openUntil = -Infinity, soft = 0, tokens = cfg.requests_per_minute, tokensAt = 0;
  const out = [];
  for (const step of sc.steps) {
    const now = step.at_seconds;
    const day = parseDate(step.date);
    const fallback = (reason) => {
      let f; try { f = fromUaq(day); } catch { f = fromTabular(day); }
      return result(f, { source: 'local-fallback', fallback_reason: reason });
    };
    const fromEntry = (e, source, reason) => result(local('aladhan', e.hijri), { source, fallback_reason: reason || null });
    if (!cfg.enabled) { out.push(fallback('disabled')); continue; }
    if (day < WINDOW_MIN || day > WINDOW_MAX) { out.push(fallback('date-outside-remote-window')); continue; }
    const hit = cache.get(day);
    if (hit && now - hit.at < cfg.ttl_seconds) { out.push(fromEntry(hit, 'remote')); continue; }
    let failure = null;
    if (now < openUntil) failure = 'circuit-open';
    else {
      tokens = Math.min(cfg.requests_per_minute, tokens + ((now - tokensAt) * cfg.requests_per_minute) / 60); tokensAt = now;
      if (tokens < 1) failure = 'outbound-rate-limited';
      else {
        tokens -= 1;
        const r = step.remote || { kind: 'network-error' };
        const hard = (reason, retry) => { failure = reason; const wait = retry != null ? Math.min(retry, cfg.max_retry_after_seconds) : cfg.cooldown_seconds; openUntil = now + wait; };
        const softf = (reason) => { failure = reason; soft += 1; if (soft >= cfg.soft_failure_limit) openUntil = now + cfg.cooldown_seconds; };
        if (r.kind === 'timeout') hard('timeout');
        else if (r.kind === 'network-error' || r.kind === 'unreachable') hard('network-error');
        else if (r.kind === 'http') {
          if (r.status === 429) hard('upstream-rate-limited', r.retry_after);
          else if (r.status >= 500) hard('upstream-server-error', r.retry_after);
          else if (r.status !== 200) softf('upstream-rejected');
        }
        if (!failure && (r.kind === 'malformed' || r.kind === 'oversize')) softf('malformed-response');
        if (!failure && r.kind === 'echo-mismatch') softf('date-mismatch');
        if (!failure && (r.kind === 'ok' || (r.kind === 'http' && r.status === 200))) {
          const h = r.hijri;
          if (!h || !(h.year >= 1 && h.year <= 1700 && h.month >= 1 && h.month <= 12 && h.day >= 1 && h.day <= 30)) softf('malformed-response');
          else {
            const delta = Math.abs(T.tabularToDay(h.year, h.month, h.day) - day);
            if (delta > cfg.max_plausible_delta_days) softf('implausible-response');
            else { soft = 0; cache.set(day, { hijri: h, at: now }); out.push(fromEntry({ hijri: h }, 'remote')); continue; }
          }
        }
      }
    }
    const stale = cache.get(day);
    if (stale && now - stale.at < cfg.max_stale_seconds) { out.push(fromEntry(stale, 'remote-stale', failure)); continue; }
    out.push(fallback(failure));
  }
  return out;
}
