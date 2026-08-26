/**
 * api.js — the ONLY layer that talks to the Python backend.
 *
 * No other JS file should call fetch() directly: if a route changes in
 * src/web/api.py, only this file has to follow.
 *
 * Every function returns a Promise and THROWS on failure. The thrown
 * Error carries an extra `code` property whenever the server sent one
 * (see src/web/errors.py) — that is the translation key, which lets the
 * caller show the message in the language the user picked instead of
 * the English text the server produced.
 */

import { t } from './i18n.js';

/**
 * fetch wrapper with standardized error handling.
 * @param {string} url
 * @param {RequestInit} options
 * @returns {Promise<any>} JSON body, or null for empty responses.
 */
async function request(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    throw await buildError(response);
  }

  if (response.status === 204) return null;
  return response.json();
}

/**
 * Turns a failed response into an Error carrying the best message
 * available, in this order:
 *
 *   1. the translation of `code`, when the server sent one
 *   2. `detail`, the server's English sentence
 *   3. a generic message with the HTTP status
 */
async function buildError(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    /* response without JSON — fall through to the generic message */
  }

  const code = body?.code;
  let message;

  if (code) {
    message = t(code, body?.params);
  } else if (typeof body?.detail === 'string') {
    message = body.detail;
  } else if (body?.detail) {
    // Pydantic validation errors arrive as a list of objects.
    message = JSON.stringify(body.detail);
  } else {
    message = t('api.generic', { status: response.status });
  }

  const error = new Error(message);
  error.code = code;
  error.status = response.status;
  return error;
}

/** POST/PATCH/PUT with a JSON body. */
function sendJson(url, method, body) {
  return request(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export const api = {
  // ---------------------------------------------------------------- //
  // Credential vault (security/env_vault.py) — the lock screen and the
  // "Exit application" button. Called before anything else in app.js.
  // ---------------------------------------------------------------- //

  /** { unlocked, first_run } — whether to show the lock screen, and in
   * which mode (choose a new password vs. enter the existing one). */
  getLockStatus: () => request('/api/lock'),

  /** Unlocks (or, on first run, creates) the encrypted credential
   * store and starts the real backend. `confirm` is only sent — and
   * only checked server-side — on first run. */
  unlock: (password, confirm) => sendJson('/api/unlock', 'POST', { password, confirm }),

  /** Gracefully stops the backend and terminates the process. */
  shutdown: () => request('/api/shutdown', { method: 'POST' }),

  // ---------------------------------------------------------------- //
  // General state (polled in a loop by app.js)
  // ---------------------------------------------------------------- //

  /** Cameras + alerts + narrator summary, in a single request. */
  getState: () => request('/api/state'),

  /** Device, notification channels and counts — only changes on restart. */
  getSystem: () => request('/api/system'),

  // ---------------------------------------------------------------- //
  // Video
  //
  // These do not use fetch: they are URLs placed straight into the src
  // of an <img>. MJPEG is a continuous stream, so the browser handles
  // the "streaming" itself.
  // ---------------------------------------------------------------- //

  /**
   * URL of the live video.
   * @param {string} cameraId
   * @param {{width?: number, quality?: number, fps?: number, overlay?: boolean}} opts
   */
  streamUrl(cameraId, { width = 900, quality = 70, fps = 15, overlay = true } = {}) {
    const params = new URLSearchParams({ width, quality, fps, overlay });
    return `/api/cameras/${encodeURIComponent(cameraId)}/stream?${params}`;
  },

  /**
   * URL of a single frame.
   * `cacheBust` forces the browser to fetch again instead of reusing the
   * cached image — without it, "Capture frame" would always return the
   * same instant.
   */
  snapshotUrl(cameraId, { overlay = false, width = 0, quality = 90, cacheBust = true } = {}) {
    const params = new URLSearchParams({ overlay, width, quality });
    if (cacheBust) params.set('t', Date.now());
    return `/api/cameras/${encodeURIComponent(cameraId)}/snapshot?${params}`;
  },

  // ---------------------------------------------------------------- //
  // Tasks (config/tasks.yaml)
  // ---------------------------------------------------------------- //

  /** Available types + the geometry kind of each one. */
  getTaskTypes: () => request('/api/task-types'),

  getTasks: (cameraId) => request(`/api/cameras/${encodeURIComponent(cameraId)}/tasks`),

  addTask: (cameraId, type) =>
    sendJson(`/api/cameras/${encodeURIComponent(cameraId)}/tasks`, 'POST', { type }),

  /** Updates detect_fps and/or params. Omitted fields stay as they are. */
  updateTask: (cameraId, index, patch) =>
    sendJson(`/api/cameras/${encodeURIComponent(cameraId)}/tasks/${index}`, 'PATCH', patch),

  deleteTask: (cameraId, index) =>
    request(`/api/cameras/${encodeURIComponent(cameraId)}/tasks/${index}`, { method: 'DELETE' }),

  saveFlags: (cameraId, index, flags) =>
    sendJson(`/api/cameras/${encodeURIComponent(cameraId)}/tasks/${index}/flags`, 'PUT', { flags }),

  /**
   * Saves the line/zone drawn on the calibration screen.
   * @param {Array<[number, number]>} points pixels at native resolution
   */
  saveGeometry: (cameraId, index, { points, zoneName, expectedClass }) =>
    sendJson(`/api/cameras/${encodeURIComponent(cameraId)}/tasks/${index}/geometry`, 'POST', {
      points,
      zone_name: zoneName ?? null,
      expected_class: expectedClass ?? null,
    }),

  /** Rebuilds the pipelines with the current tasks.yaml, no restart. */
  reload: () => request('/api/reload', { method: 'POST' }),

  // ---------------------------------------------------------------- //
  // Camera registry (config/cameras.yaml + the encrypted .env vault)
  // ---------------------------------------------------------------- //

  /** Connection details of every camera (no passwords) — host, port,
   * protocol, path, username. Backs the "Add camera" panel and the
   * hyperlinked host on each card. */
  getCameras: () => request('/api/cameras'),

  /** Full details of ONE camera, INCLUDING its password — only called
   * when the cog button's settings panel is opened. */
  getCamera: (cameraId) => request(`/api/cameras/${encodeURIComponent(cameraId)}`),

  /**
   * Registers a new camera: builds the connection string server-side
   * and writes both cameras.yaml and the encrypted .env vault.
   * @param {{id?: string, name: string, protocol: string, host: string,
   *   port?: number, path?: string, username?: string, password?: string,
   *   enabled?: boolean}} payload
   */
  addCamera: (payload) => sendJson('/api/cameras', 'POST', payload),

  /** Absent fields are left untouched — the settings panel only sends
   * what changed. */
  updateCamera: (cameraId, patch) =>
    sendJson(`/api/cameras/${encodeURIComponent(cameraId)}`, 'PATCH', patch),

  /** Stops the camera's stream and removes it from cameras.yaml. */
  deleteCamera: (cameraId) =>
    request(`/api/cameras/${encodeURIComponent(cameraId)}`, { method: 'DELETE' }),

  // ---------------------------------------------------------------- //
  // Employees (face recognition)
  // ---------------------------------------------------------------- //

  getEmployees: () => request('/api/employees'),

  /**
   * Enrolls an employee. Sends multipart because it may carry an image
   * file — hence FormData instead of JSON.
   * @param {{name: string, cameraId?: string, file?: File}} data
   */
  enrollEmployee({ name, cameraId, file }) {
    const form = new FormData();
    form.append('name', name);
    if (cameraId) form.append('camera_id', cameraId);
    if (file) form.append('photo', file);
    return request('/api/employees', { method: 'POST', body: form });
  },
};
