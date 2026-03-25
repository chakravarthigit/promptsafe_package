/**
 * PromptSafe — Main Entry Point (Node.js)
 * Public API: scan, isSafe, block, getLogs, getStats, configure
 */

'use strict';

const { scan: _detectScan, addPattern } = require('./detector');
const AttackLogger = require('./logger');

let _config = { threshold: 35 };
let _logger = null;

function getLogger() {
  if (!_logger) _logger = new AttackLogger();
  return _logger;
}

/**
 * Scan text for prompt injection.
 *
 * @param {string} text - Input text to scan.
 * @param {Object} [options]
 * @param {boolean} [options.log=true] - Log detected attacks locally.
 * @returns {{ input, score, isSafe, riskLevel, reasons, matchedPatterns }}
 *
 * @example
 * const result = promptsafe.scan("ignore previous instructions");
 * console.log(result.isSafe);    // false
 * console.log(result.score);     // 70
 * console.log(result.riskLevel); // "high"
 */
function scan(text, options = {}) {
  const logAttacks = options.log !== false;
  const result = _detectScan(text, { threshold: _config.threshold });

  if (logAttacks && !result.isSafe) {
    getLogger().log({
      input: result.input,
      score: result.score,
      riskLevel: result.riskLevel,
      reasons: result.reasons,
      isBlocked: true,
    });
  }

  return result;
}

/**
 * Quick safety check.
 * @param {string} text
 * @param {Object} [options]
 * @returns {boolean} true if safe
 */
function isSafe(text, options = {}) {
  return scan(text, options).isSafe;
}

/**
 * Scan and return text if safe, throw if unsafe.
 * @param {string} text
 * @param {Object} [options]
 * @returns {string} Original text if safe.
 * @throws {Error} PromptInjectionError if unsafe.
 */
function block(text, options = {}) {
  const result = scan(text, options);
  if (!result.isSafe) {
    const err = new Error(
      `Prompt injection detected (score=${result.score}, risk=${result.riskLevel}): ` +
        result.reasons.slice(0, 3).join('; ')
    );
    err.name = 'PromptInjectionError';
    err.result = result;
    throw err;
  }
  return text;
}

/**
 * Get recent attack logs.
 * @param {Object} [options]
 * @param {number} [options.limit=50]
 * @param {string} [options.riskLevel]
 * @returns {Object[]}
 */
function getLogs(options = {}) {
  return getLogger().getRecent(options.limit || 50, options.riskLevel || null);
}

/**
 * Get aggregate attack statistics.
 * @returns {Object}
 */
function getStats() {
  return getLogger().getStats();
}

/**
 * Configure PromptSafe globally.
 * @param {Object} options
 * @param {number} [options.threshold=35] - Score threshold (0-100).
 * @param {string} [options.logFile] - Custom log file path.
 *
 * @example
 * promptsafe.configure({ threshold: 50 }); // more lenient
 */
function configure(options = {}) {
  if (options.threshold !== undefined) _config.threshold = options.threshold;
  if (options.logFile) _logger = new AttackLogger(options.logFile);
}

module.exports = {
  scan,
  isSafe,
  block,
  getLogs,
  getStats,
  configure,
  addPattern,
  version: '1.0.0',
};
