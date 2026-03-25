#!/usr/bin/env node
/**
 * PromptSafe CLI (npx promptsafe)
 * Usage:
 *   npx promptsafe "text to scan"
 *   npx promptsafe scan file.txt
 *   npx promptsafe logs [--limit N] [--risk LEVEL]
 *   npx promptsafe stats
 */

'use strict';

const fs = require('fs');
const path = require('path');
const promptsafe = require('../src/index');

// ANSI colors
const C = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  green: '\x1b[92m',
  red: '\x1b[91m',
  yellow: '\x1b[93m',
  cyan: '\x1b[96m',
  magenta: '\x1b[95m',
};

const RISK_COLORS = {
  safe: C.green,
  low: C.cyan,
  medium: C.yellow,
  high: C.magenta,
  critical: C.red,
};

const supportsColor = process.stdout.isTTY;
const c = (text, color) => (supportsColor ? `${color}${text}${C.reset}` : text);
const line = (ch = '─', n = 52) => c(ch.repeat(n), C.dim);

function printResult(result, title = 'Scan Result') {
  const riskColor = RISK_COLORS[result.riskLevel] || C.reset;
  const verdict = result.isSafe
    ? c('✅  SAFE', C.green)
    : c('🚨  BLOCKED', C.red);

  console.log();
  console.log(c(`  PromptSafe — ${title}`, C.bold + C.cyan));
  console.log(line());
  console.log(`  ${'Verdict'.padEnd(14)} ${verdict}`);
  console.log(`  ${'Score'.padEnd(14)} ${c(`${result.score} / 100`, riskColor)}`);
  console.log(`  ${'Risk Level'.padEnd(14)} ${c(result.riskLevel.toUpperCase(), riskColor)}`);

  if (result.reasons && result.reasons.length) {
    console.log(`  ${'Reasons'.padEnd(14)}`);
    const reasons = result.reasons.slice(0, 5);
    reasons.forEach((r, i) => {
      console.log(`  ${''.padEnd(14)}  ${c(`${i + 1}.`, C.dim)} ${r}`);
    });
    if (result.reasons.length > 5) {
      console.log(`  ${''.padEnd(14)}  ${c(`... and ${result.reasons.length - 5} more`, C.dim)}`);
    }
  }
  console.log(line());
  console.log();
}

function printLogEntry(entry, index) {
  const riskColor = RISK_COLORS[entry.riskLevel] || C.reset;
  const blocked = entry.isBlocked ? '🚨 BLOCKED' : '✅ SAFE';
  const preview = (entry.input || '').slice(0, 80) + (entry.input && entry.input.length > 80 ? '...' : '');
  const ts = entry.timestamp || 'N/A';

  console.log(
    `  ${c(String(index).padEnd(3), C.dim)} [${ts}] ` +
    `${c((entry.riskLevel || '?').toUpperCase(), riskColor)} ` +
    `score=${entry.score} ${blocked}`
  );
  console.log(`     ${c(preview, C.dim)}`);
}

// ─── Commands ───────────────────────────────────────────────────────────────

function cmdScanText(text, opts = {}) {
  const result = promptsafe.scan(text, { log: true });
  if (opts.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printResult(result);
  }
  process.exit(result.isSafe ? 0 : 1);
}

function cmdScanFile(filePath, opts = {}) {
  if (!fs.existsSync(filePath)) {
    console.error(c(`  ❌ File not found: ${filePath}`, C.red));
    process.exit(2);
  }
  const content = fs.readFileSync(filePath, 'utf8');
  const result = promptsafe.scan(content, { log: true });

  if (opts.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printResult(result, `File Scan: ${path.basename(filePath)}`);
  }
  process.exit(result.isSafe ? 0 : 1);
}

function cmdLogs(opts = {}) {
  const entries = promptsafe.getLogs({
    limit: opts.limit || 20,
    riskLevel: opts.risk || null,
  });

  if (opts.json) {
    console.log(JSON.stringify(entries, null, 2));
    return;
  }

  console.log();
  console.log(c(`  PromptSafe — Recent Logs (${entries.length} entries)`, C.bold + C.cyan));
  console.log(line('─', 62));

  if (!entries.length) {
    console.log(c('  No attack logs found.', C.dim));
  } else {
    entries.forEach((e, i) => printLogEntry(e, i + 1));
  }

  console.log(line('─', 62));
  console.log();
}

function cmdStats(opts = {}) {
  const stats = promptsafe.getStats();

  if (opts.json) {
    console.log(JSON.stringify(stats, null, 2));
    return;
  }

  console.log();
  console.log(c('  PromptSafe — Statistics', C.bold + C.cyan));
  console.log(line('─', 42));
  console.log(`  ${'Total Scanned'.padEnd(20)} ${stats.totalScanned}`);
  console.log(`  ${'Total Blocked'.padEnd(20)} ${c(String(stats.totalBlocked), C.red)}`);
  console.log(`  ${'Total Safe'.padEnd(20)} ${c(String(stats.totalSafe), C.green)}`);
  console.log();
  const byRisk = stats.byRiskLevel || {};
  if (Object.keys(byRisk).length) {
    console.log(c('  By Risk Level:', C.bold));
    Object.entries(byRisk).sort().forEach(([lvl, cnt]) => {
      const rc = RISK_COLORS[lvl] || C.reset;
      console.log(`    ${c(lvl.toUpperCase().padEnd(12), rc)} ${cnt}`);
    });
  }
  console.log(line('─', 42));
  console.log(c(`  Log: ${stats.logFile}`, C.dim));
  console.log();
}

// ─── CLI Parsing ─────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

if (!args.length || args[0] === '--help' || args[0] === '-h') {
  console.log(`
  ${c('🛡️  PromptSafe', C.bold + C.cyan)} v${promptsafe.version}
  Lightweight AI prompt injection shield

  ${c('Usage:', C.bold)}
    npx promptsafe "text to scan"
    npx promptsafe scan <file>
    npx promptsafe logs [--limit N] [--risk LEVEL]
    npx promptsafe stats

  ${c('Options:', C.bold)}
    --json        Output results as JSON
    --limit N     Number of log entries (default: 20)
    --risk LEVEL  Filter logs by risk (safe|low|medium|high|critical)
    --version     Show version
    --help        Show this help
  `);
  process.exit(0);
}

if (args[0] === '--version' || args[0] === '-v') {
  console.log(`promptsafe/${promptsafe.version}`);
  process.exit(0);
}

// Parse flags
const jsonFlag = args.includes('--json');
const limitIdx = args.indexOf('--limit');
const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1], 10) || 20 : 20;
const riskIdx = args.indexOf('--risk');
const risk = riskIdx !== -1 ? args[riskIdx + 1] : null;

const cmd = args[0];

if (cmd === 'scan') {
  const file = args[1];
  if (!file) {
    console.error(c('  ❌ Please provide a file path: npx promptsafe scan <file>', C.red));
    process.exit(1);
  }
  cmdScanFile(file, { json: jsonFlag });

} else if (cmd === 'logs') {
  cmdLogs({ limit, risk, json: jsonFlag });

} else if (cmd === 'stats') {
  cmdStats({ json: jsonFlag });

} else {
  // Treat as inline text
  const text = args.filter(a => !a.startsWith('--')).join(' ');
  if (!text) {
    console.error(c('  ❌ Please provide text to scan.', C.red));
    process.exit(1);
  }
  cmdScanText(text, { json: jsonFlag });
}
