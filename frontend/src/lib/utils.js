import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes with proper precedence
 * @param  {...any} inputs 
 * @returns {string}
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Format a score to one decimal place
 * @param {number} score 
 * @returns {string}
 */
export function formatScore(score) {
  return (score || 0).toFixed(1);
}

/**
 * Get score badge variant based on score value
 * @param {number} score 
 * @returns {'high' | 'mid' | 'low'}
 */
export function getScoreVariant(score) {
  if (score >= 7.5) return 'high';
  if (score >= 5.5) return 'mid';
  return 'low';
}

/**
 * Get color class for score
 * @param {number} score 
 * @returns {string}
 */
export function getScoreColor(score) {
  if (score >= 7.5) return 'text-veridian';
  if (score >= 5.5) return 'text-semantic-warning';
  return 'text-semantic-error';
}

/**
 * Get background color class for score
 * @param {number} score 
 * @returns {string}
 */
export function getScoreBg(score) {
  if (score >= 7.5) return 'bg-veridian-subtle';
  if (score >= 5.5) return 'bg-semantic-warning-bg';
  return 'bg-semantic-error-bg';
}

/**
 * Get verdict text based on score
 * @param {number} score 
 * @returns {string}
 */
export function getVerdict(score) {
  if (score >= 8) return 'EXCELLENT';
  if (score >= 6.5) return 'SOLID';
  if (score >= 5) return 'BORDERLINE';
  return 'NEEDS WORK';
}

/**
 * Get verdict color based on score
 * @param {number} score 
 * @returns {string}
 */
export function getVerdictColor(score) {
  if (score >= 8) return 'bg-veridian-subtle text-veridian';
  if (score >= 6.5) return 'bg-veridian-subtle text-veridian';
  if (score >= 5) return 'bg-semantic-warning-bg text-semantic-warning';
  return 'bg-semantic-error-bg text-semantic-error';
}

/**
 * Format duration in minutes to readable string
 * @param {number} minutes 
 * @returns {string}
 */
export function formatDuration(minutes) {
  return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
}

/**
 * Stagger animation delay helper
 * @param {number} index 
 * @param {number} baseDelay 
 * @returns {object}
 */
export function staggerDelay(index, baseDelay = 80) {
  return { animationDelay: `${index * baseDelay}ms` };
}
