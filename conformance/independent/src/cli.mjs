#!/usr/bin/env node
// cli.mjs -- COP adapter process.  stdin: {"cases":[{id,op,input}...]}  stdout: {"implementation":{...},"results":[...]}
//   node src/cli.mjs --describe     prints the implementation descriptor + supported operations
import fs from 'node:fs';
import { runCase, CAPABILITIES } from './ops.mjs';

const DESCRIPTOR = {
  name: 'waqt-independent', version: '0.1.0', language: 'JavaScript (Node.js, zero dependencies)',
  cop_version: '1.1',
  astronomy: { sun: 'truncated VSOP87D (Earth) + FK5 + nutation + aberration', timescale: 'Espenak-Meeus 2006 DeltaT', events: 'scan-and-bisect on the true altitude function', moon: 'truncated ELP2000-82 / Meeus ch.47' },
  timezone_source: 'ICU (Intl.DateTimeFormat) tz database',
  shares_code_with_reference: false,
};
if (process.argv.includes('--describe')) {
  process.stdout.write(JSON.stringify({ implementation: DESCRIPTOR, operations: CAPABILITIES }) + '\n');
} else {
  const req = JSON.parse(fs.readFileSync(0, 'utf8'));
  const results = req.cases.map(runCase);
  process.stdout.write(JSON.stringify({ implementation: DESCRIPTOR, results }) + '\n');
}
