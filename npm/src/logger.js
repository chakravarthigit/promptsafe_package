'use strict';

/**
 * PromptSafe — Attack Logger (Node.js)
 * Logs detected prompt injection attacks to a local JSON file.
 * Zero external dependencies.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const DEFAULT_LOG_FILE = path.join(os.homedir(), '.promptsafe', 'attacks.json');

class AttackLogger {
  /**
   * @param {string} [logFile] - Path to the JSON log file.
   */
  constructor(logFile) {
    this.logFile = logFile || DEFAULT_LOG_FILE;
    this._ensureDir();
  }

  // ── Internals ──────────────────────────────────────────────────────────────

  _ensureDir() {
    const dir = path.dirname(this.logFile);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  _readAll() {
    if (!fs.existsSync(this.logFile)) return [];
    try {
      return JSON.parse(fs.readFileSync(this.logFile, 'utf8'));
    } catch {
      return [];
    }
  }

  _writeAll(entries) {
    fs.writeFileSync(this.logFile, JSON.stringify(entries, null, 2), 'utf8');
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Append an attack event to the log.
   * @param {{ input, score, riskLevel, reasons, isBlocked }} event
   */
  log(event) {
    const entries = this._readAll();
    entries.unshift({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      input: (event.input || '').slice(0, 500),
      score: event.score || 0,
      riskLevel: event.riskLevel || 'unknown',
      reasons: event.reasons || [],
      isBlocked: event.isBlocked !== false,
    });
    // Keep last 1000 entries
    this._writeAll(entries.slice(0, 1000));
  }

  /**
   * Get recent log entries, newest first.
   * @param {number} [limit=50]
   * @param {string|null} [riskLevel]
   * @returns {Object[]}
   */
  getRecent(limit = 50, riskLevel = null) {
    let entries = this._readAll();
    if (riskLevel) {
      entries = entries.filter(e => e.riskLevel === riskLevel);
    }
    return entries.slice(0, limit);
  }

  /**
   * Get aggregate statistics.
   * @returns {{ totalScanned, totalBlocked, totalSafe, byRiskLevel, logFile }}
   */
  getStats() {
    const entries = this._readAll();
    const byRisk = {};
    let blocked = 0;
    for (const e of entries) {
      if (e.isBlocked) blocked++;
      byRisk[e.riskLevel] = (byRisk[e.riskLevel] || 0) + 1;
    }
    return {
      totalScanned: entries.length,
      totalBlocked: blocked,
      totalSafe: entries.length - blocked,
      byRiskLevel: byRisk,
      logFile: this.logFile,
    };
  }

  /**
   * Delete all log entries.
   * @returns {number} Number of entries deleted.
   */
  clear() {
    const count = this._readAll().length;
    this._writeAll([]);
    return count;
  }
}

module.exports = AttackLogger;
