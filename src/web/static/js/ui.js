/**
 * ui.js — interface helpers used by every screen.
 *
 * No framework: `el()` creates elements, `$`/`$$` query the DOM and
 * `toast()` shows notices. These few functions replace what a
 * React/Vue would do here, keeping the project free of a build step.
 */

import { t } from './i18n.js';

/** First element matching the selector. */
export const $ = (selector, scope = document) => scope.querySelector(selector);

/** Every matching element, already an Array (so .map works). */
export const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

/**
 * Creates an element with attributes and children in a single call.
 *
 *   el('div', { class: 'card' }, el('h2', {}, 'Title'), 'loose text')
 *
 * Special attributes:
 *   class / className  CSS class
 *   dataset            object of data-* values (e.g. {id: 'cam1'})
 *   on<Event>          listener (e.g. onClick: () => ...)
 *   anything else      becomes an HTML attribute; `false`/`null` skips it
 *
 * @param {string} tag
 * @param {object} attrs
 * @param {...(Node|string|null|false)} children
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;

    if (key === 'class' || key === 'className') {
      node.className = value;
    } else if (key === 'dataset') {
      Object.assign(node.dataset, value);
    } else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === 'text') {
      node.textContent = value;
    } else {
      node.setAttribute(key, value === true ? '' : value);
    }
  }

  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  return node;
}

/** Removes every child of an element (faster than innerHTML=''). */
export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/** Shows/hides through the HTML `hidden` attribute. */
export function setVisible(node, visible) {
  node.hidden = !visible;
}

/**
 * Temporary notice at the bottom of the screen.
 * @param {string} message already-translated text
 * @param {'info'|'success'|'error'} kind
 * @param {number} duration ms before it disappears (errors linger)
 */
export function toast(message, kind = 'info', duration = kind === 'error' ? 6000 : 3200) {
  const container = $('#toasts');
  if (!container) return;

  const node = el('div', { class: `toast toast--${kind}` }, message);
  container.append(node);

  setTimeout(() => {
    node.classList.add('is-leaving');
    node.addEventListener('animationend', () => node.remove(), { once: true });
  }, duration);
}

/**
 * Runs a promise and shows the error as a toast if it fails.
 * The message is already translated by api.js.
 */
export async function guard(promise, { onError } = {}) {
  try {
    return await promise;
  } catch (error) {
    toast(error.message, 'error');
    if (onError) onError(error);
    return null;
  }
}

// ---------------------------------------------------------------------- //
// Formatting
// ---------------------------------------------------------------------- //

/** Epoch seconds -> "14:32:07". */
export function formatTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString(undefined, { hour12: false });
}

/** Epoch seconds -> "12s ago" / "4min ago" / "2h ago", translated. */
export function formatRelative(epochSeconds) {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (seconds < 60) return t('time.seconds', { value: seconds });
  if (seconds < 3600) return t('time.minutes', { value: Math.floor(seconds / 60) });
  if (seconds < 86400) return t('time.hours', { value: Math.floor(seconds / 3600) });
  return t('time.days', { value: Math.floor(seconds / 86400) });
}

/**
 * {person: 3, bottle: 1} -> "3 person · 1 bottle"
 * Class names come from the YOLO model, so they are never translated.
 */
export function formatCounts(classCounts) {
  const entries = Object.entries(classCounts || {});
  if (entries.length === 0) return '';
  return entries
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => `${count} ${name}`)
    .join(' · ');
}

/** Initials for the employee list avatar: "Ana Souza" -> "AS". */
export function initials(name) {
  return (name || '?')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

/**
 * Fills a <select> with options.
 * Keeps the selected value when it still exists in the new list — this
 * stops a periodic refresh from resetting the user's choice.
 *
 * @param {HTMLSelectElement} select
 * @param {Array<{value: string, label: string}>} options
 */
export function fillSelect(select, options) {
  const previous = select.value;
  clear(select);

  for (const { value, label } of options) {
    select.append(el('option', { value }, label));
  }

  if (options.some((option) => String(option.value) === previous)) {
    select.value = previous;
  }
}
