/**
 * i18n.js — translation for the web interface.
 *
 * The catalog is NOT stored here: it is fetched once from
 * GET /api/i18n, which serves src/i18n.py. That is deliberate — the
 * desktop GUI reads the same file, so wording is edited in exactly one
 * place and never drifts between the two interfaces.
 *
 * Switching language does not reload the page. `setLanguage()` swaps the
 * active dictionary, re-runs `applyTranslations()` over the static
 * markup and notifies every listener registered with
 * `onLanguageChange()` so the dynamic screens redraw themselves.
 *
 * How a string gets translated:
 *
 *   static markup   add data-i18n="key" to the element in index.html
 *                   (data-i18n-placeholder / data-i18n-title for those
 *                   attributes)
 *   built in JS     call t('key', { name: 'value' })
 *
 * Placeholders use {name} and match Python's str.format syntax, so the
 * very same catalog string works on both sides.
 */

/** Where the chosen language is remembered, per browser. */
const STORAGE_KEY = 'cvcentral.language';

/** Fallback used before the catalog arrives and for missing keys. */
const FALLBACK_LANGUAGE = 'en';

let catalog = {};          // { en: {key: text}, pt: {...} }
let languages = [];        // [{ code, label }]
let current = FALLBACK_LANGUAGE;

/** Callbacks to re-render dynamic screens after a language change. */
const listeners = [];

/**
 * Fetches the catalog and settles on the starting language.
 *
 * Priority: what this browser saved > what app.yaml configures >
 * English. That way a server-wide default is respected on first visit
 * without ever overriding a choice the user already made here.
 */
export async function loadCatalog() {
  const response = await fetch('/api/i18n');
  const data = await response.json();

  catalog = data.catalog ?? {};
  languages = data.languages ?? [];

  const stored = readStored();
  current = isKnown(stored) ? stored : (isKnown(data.default) ? data.default : FALLBACK_LANGUAGE);

  document.documentElement.lang = current;
  return { languages, current };
}

function isKnown(code) {
  return Boolean(code) && Object.prototype.hasOwnProperty.call(catalog, code);
}

function readStored() {
  // localStorage throws in some privacy modes — a missing preference is
  // never a reason to fail loading the page.
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(code) {
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    /* preference simply is not remembered next time */
  }
}

/** Languages offered by the server, for the picker. */
export function availableLanguages() {
  return languages;
}

export function getLanguage() {
  return current;
}

/**
 * Switches language and refreshes the whole interface in place.
 * Does nothing when the code is unknown or already active.
 */
export function setLanguage(code) {
  if (!isKnown(code) || code === current) return;

  current = code;
  writeStored(code);
  document.documentElement.lang = code;

  applyTranslations();
  for (const listener of listeners) listener(code);
}

/**
 * Registers a callback fired after every language change — used by the
 * screens that build their DOM in JavaScript and therefore cannot be
 * covered by data-i18n attributes alone.
 */
export function onLanguageChange(listener) {
  listeners.push(listener);
}

/**
 * Translates `key`, interpolating {placeholders} from `params`.
 *
 * A missing key falls back to English and then to the key itself, so an
 * untranslated string shows up as visible text instead of breaking the
 * screen.
 */
export function t(key, params) {
  const text =
    catalog[current]?.[key] ??
    catalog[FALLBACK_LANGUAGE]?.[key] ??
    key;

  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    (params[name] !== undefined ? String(params[name]) : match));
}

/**
 * Applies the catalog to the static markup inside `root`.
 *
 * Called once at startup and again on every language change. Only
 * elements carrying a data-i18n* attribute are touched, so anything
 * built by JavaScript stays untouched (those screens re-render through
 * onLanguageChange instead).
 */
export function applyTranslations(root = document) {
  for (const node of root.querySelectorAll('[data-i18n]')) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of root.querySelectorAll('[data-i18n-placeholder]')) {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  }
  for (const node of root.querySelectorAll('[data-i18n-title]')) {
    node.title = t(node.dataset.i18nTitle);
  }
}
