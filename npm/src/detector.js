'use strict';

/**
 * PromptSafe — Detection Engine (Node.js)
 * Detects prompt injection using regex + keyword scoring.
 * Zero external dependencies.
 */

const fs = require('fs');
const path = require('path');

// ─── Patterns DB ─────────────────────────────────────────────────────────────

const PATTERNS_FILE = path.join(__dirname, '..', '..', 'python', 'promptsafe', 'patterns.json');

let _db = null;
let _compiled = null;

function loadDB() {
  if (!_db) {
    const raw = fs.readFileSync(PATTERNS_FILE, 'utf8');
    _db = JSON.parse(raw);
  }
  return _db;
}

// ─── Regex Compatibility ──────────────────────────────────────────────────────

/**
 * Remove Python-style inline flags like (?i) (?s) (?m) that are not supported
 * by the Node.js RegExp constructor (which already uses the 'gis' flags).
 */
function stripInlineFlags(pattern) {
  return pattern.replace(/\(\?[imsxuLs]+\)/g, '');
}

function compilePatterns() {
  if (!_compiled) {
    const db = loadDB();
    _compiled = (db.categories || []).map(cat => {
      const regexes = [];
      for (const p of (cat.patterns || [])) {
        try {
          regexes.push(new RegExp(stripInlineFlags(p), 'gis'));
        } catch (e) {
          // skip invalid patterns
        }
      }
      return { name: cat.name, weight: cat.weight || 10, regexes };
    });
  }
  return _compiled;
}

function invalidateCache() {
  _db = null;
  _compiled = null;
}

// ─── Risk Level ───────────────────────────────────────────────────────────────

function riskLevel(score) {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  if (score >= 20) return 'low';
  return 'safe';
}

// ─── Keyword Scoring ─────────────────────────────────────────────────────────

const KEYWORD_WEIGHTS = { high: 15, medium: 8, low: 3 };

function keywordScore(text) {
  const db = loadDB();
  const keywords = db.keywords || {};
  const lc = text.toLowerCase();
  let score = 0;
  for (const [tier, weight] of Object.entries(KEYWORD_WEIGHTS)) {
    for (const kw of (keywords[tier] || [])) {
      if (lc.includes(kw.toLowerCase())) score += weight;
    }
  }
  return score;
}

// ─── Main Scanner ─────────────────────────────────────────────────────────────

/**
 * Scan text for prompt injection.
 *
 * @param {string} text
 * @param {Object} [opts]
 * @param {number} [opts.threshold=35]
 * @returns {{ input, score, isSafe, riskLevel, reasons, matchedPatterns }}
 */
function scan(text, opts = {}) {
  if (typeof text !== 'string') throw new TypeError('text must be a string');

  const threshold = opts.threshold !== undefined ? opts.threshold : 35;
  const categories = compilePatterns();

  let score = 0;
  const reasons = [];
  const matched = new Set();

  // Regex matching
  for (const cat of categories) {
    for (const rx of cat.regexes) {
      rx.lastIndex = 0; // reset for 'g' flag
      const m = rx.exec(text);
      if (m) {
        score += cat.weight;
        matched.add(cat.name);
        reasons.push(`[${cat.name}] matched: «${m[0].slice(0, 80)}»`);
        break; // one hit per category
      }
    }
  }

  // Keyword scoring
  score += keywordScore(text);

  // Cap at 100
  score = Math.min(score, 100);

  return {
    input: text.slice(0, 500),
    score,
    isSafe: score < threshold,
    riskLevel: riskLevel(score),
    reasons,
    matchedPatterns: [...matched],
  };
}

/**
 * Add a custom regex pattern at runtime.
 *
 * @param {string} category - Category name (new or existing).
 * @param {string} pattern  - JS-compatible regex string.
 * @param {number} [weight=15]
 */
function addPattern(category, pattern, weight = 15) {
  const db = loadDB();
  const existing = (db.categories || []).find(c => c.name === category);
  if (existing) {
    existing.patterns.push(pattern);
  } else {
    db.categories.push({ name: category, weight, patterns: [pattern] });
  }
  invalidateCache();
  _db = db; // keep updated DB without re-reading file
}

module.exports = { scan, addPattern };
