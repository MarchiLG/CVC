/**
 * app.js — the front-end entry point.
 *
 * Responsibilities:
 *   1. load the translation catalog and settle on the language
 *   2. initialize the four screens (js/views/*.js)
 *   3. switch the active screen when a navigation item is clicked
 *   4. run the POLLING that keeps the interface alive
 *   5. draw the alerts panel and the sidebar status
 *
 * Why polling and not a WebSocket: the backend is already synchronous
 * and keeps the "last value" of everything (results_store,
 * flag_manager.recent) — exactly like the Qt GUI, which also reads on a
 * timer (a 100ms QTimer in gui_qt/main_window.py). One request per
 * second to /api/state delivers the same result with far fewer moving
 * parts. VIDEO does not go through here: it is MJPEG straight into an
 * <img> (see views/live.js).
 */

import { api } from './api.js';
import {
  applyTranslations,
  availableLanguages,
  getLanguage,
  loadCatalog,
  onLanguageChange,
  setLanguage,
  t,
} from './i18n.js';
import { $, $$, clear, el, formatRelative, formatTime, setVisible, toast } from './ui.js';
import { calibrationView } from './views/calibration.js';
import { employeesView } from './views/employees.js';
import { liveView } from './views/live.js';
import { settingsView } from './views/settings.js';
import { triggersView } from './views/triggers.js';

/** Polling interval for /api/state, in ms. */
const POLL_INTERVAL = 1000;

/** The five screens, in the order they appear in the sidebar. */
const VIEWS = ['live', 'calibration', 'settings', 'employees', 'triggers'];

const app = {
  currentView: 'live',
  alertFilter: 'all',
  /** Timestamp of the newest alert already seen — the basis for
   *  detecting what is new. The COUNT cannot be used: the backend
   *  returns at most 100 alerts (flag_manager.recent), so beyond that
   *  the total stops growing even as new alerts arrive. */
  newestAlertSeen: 0,
  /** False until the first cycle completes: the history that already
   *  exists when the page opens must not become a flood of toasts. */
  alertsPrimed: false,
  pollTimer: null,

  /**
   * Entry point (called once, at the bottom of this file). Decides
   * between the lock screen and the real app BEFORE anything backend-
   * shaped happens — the web app now starts with no AppRuntime at all
   * (see web/server.py), specifically so it can be opened by
   * double-clicking run-html.sh with no terminal to type a password
   * into. GET /api/lock and /api/i18n both work in that locked state;
   * everything else (state, cameras, tasks...) does not yet.
   */
  async boot() {
    // The catalog has to arrive BEFORE anything renders, otherwise the
    // first paint (lock screen included) would show raw translation
    // keys. Safe to call even while locked — see GET /api/i18n.
    await this.setupLanguage();
    this.bindExitButtons();

    let status;
    try {
      status = await api.getLockStatus();
    } catch {
      // The server itself is not answering yet (e.g. still binding the
      // port right after launch) — assume unlocked and let start()'s
      // own polling/offline handling take over on the next tick.
      status = { unlocked: true, first_run: false };
    }

    if (status.unlocked) {
      this.enterApp();
    } else {
      this.showLockScreen(status.first_run);
    }
  },

  async start() {
    liveView.init();
    calibrationView.init();
    settingsView.init();
    employeesView.init();
    triggersView.init();

    this.bindNavigation();
    this.bindAlertsPanel();

    await this.loadStaticData();

    // First load immediately, then on an interval.
    await this.poll();
    this.pollTimer = setInterval(() => this.poll(), POLL_INTERVAL);

    // Close the MJPEG streams when the tab loses focus: without this,
    // every open tab holds one connection per camera on the server.
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) liveView.suspend();
      else liveView.resume();
    });
  },

  // ------------------------------------------------------------------ //
  // Lock screen (POST /api/unlock, src/security/env_vault.py)
  // ------------------------------------------------------------------ //
  showLockScreen(firstRun) {
    setVisible($('#app-shell'), false);
    setVisible($('#lock-screen'), true);

    $('#lock-subtitle').textContent = t(firstRun ? 'lock.subtitle_first_run' : 'lock.subtitle_unlock');
    setVisible($('#lock-confirm-field'), firstRun);
    $('#lock-submit').textContent = t(firstRun ? 'lock.create' : 'lock.unlock');
    $('#lock-password').focus();

    // Bound once: submitUnlock() re-reads #lock-confirm-field's
    // visibility on every submit, so re-binding on retry is not needed.
    $('#lock-form').addEventListener('submit', (event) => this.submitUnlock(event));
  },

  async submitUnlock(event) {
    event.preventDefault();

    const passwordInput = $('#lock-password');
    const firstRun = !$('#lock-confirm-field').hidden;
    const password = passwordInput.value;
    const confirm = firstRun ? $('#lock-confirm').value : undefined;

    if (firstRun && password !== confirm) {
      this.showLockError(t('api.password_mismatch'));
      return;
    }

    const submitBtn = $('#lock-submit');
    const originalLabel = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = t('lock.starting');
    this.showLockError('');

    try {
      await api.unlock(password, confirm);
      this.enterApp();
    } catch (error) {
      this.showLockError(error.message);

      if (error.code === 'api.too_many_attempts') {
        // The server already triggered its own shutdown — nothing left
        // to retry, so the form stays disabled instead of resetting.
        passwordInput.disabled = true;
        $('#lock-exit').disabled = true;
        return;
      }

      submitBtn.disabled = false;
      submitBtn.textContent = originalLabel;
      passwordInput.value = '';
      passwordInput.focus();
    }
  },

  showLockError(message) {
    const node = $('#lock-error');
    node.textContent = message;
    setVisible(node, Boolean(message));
  },

  enterApp() {
    setVisible($('#lock-screen'), false);
    setVisible($('#app-shell'), true);
    this.start();
  },

  // ------------------------------------------------------------------ //
  // "Exit application" — stops the backend and the Python process
  // itself (POST /api/shutdown), for when there is no terminal to
  // Ctrl+C because the app was started by double-clicking run-html.sh.
  // ------------------------------------------------------------------ //
  bindExitButtons() {
    for (const button of [$('#exit-app-btn'), $('#lock-exit')]) {
      button.addEventListener('click', () => this.requestShutdown());
    }
  },

  async requestShutdown() {
    if (!window.confirm(t('app.exit_confirm'))) return;

    try {
      await api.shutdown();
    } catch {
      // The connection dropping mid-response, as the process exits, IS
      // the expected outcome here — not a failure to report.
    }
    this.showShuttingDown();
  },

  showShuttingDown() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    liveView.suspend();

    setVisible($('#app-shell'), false);
    const screen = $('#lock-screen');
    clear(screen);
    screen.append(el('div', { class: 'lock-card lock-card--message' }, t('app.exiting')));
    setVisible(screen, true);
  },

  // ------------------------------------------------------------------ //
  // Language
  // ------------------------------------------------------------------ //

  /**
   * Loads the catalog, fills the picker and wires up the switch.
   *
   * Screens that build their DOM in JavaScript cannot be covered by
   * data-i18n attributes, so each one exposes a `retranslate()` that
   * runs on every language change.
   */
  async setupLanguage() {
    try {
      await loadCatalog();
    } catch {
      // Without the catalog, t() falls back to the keys themselves —
      // ugly, but the interface still works.
      toast('Failed to load translations.', 'error');
    }

    applyTranslations();

    const select = $('#language-select');
    clear(select);
    for (const { code, label } of availableLanguages()) {
      select.append(el('option', { value: code, selected: code === getLanguage() }, label));
    }
    select.addEventListener('change', () => setLanguage(select.value));

    onLanguageChange(() => {
      this.updateViewHeader();
      liveView.retranslate();
      calibrationView.retranslate();
      settingsView.retranslate();
      employeesView.retranslate();
      triggersView.retranslate();
      this.renderAlerts(this.lastAlerts ?? []);
      this.renderSystemStatus();
    });
  },

  // ------------------------------------------------------------------ //
  // Navigation between screens
  // ------------------------------------------------------------------ //
  bindNavigation() {
    for (const button of $$('.nav__item')) {
      button.addEventListener('click', () => this.showView(button.dataset.view));
    }

    // Hash routing (#calibration, #settings, ...): the browser back
    // button works, reloading keeps the tab open, and a link can point
    // straight at one screen.
    window.addEventListener('hashchange', () => this.showView(this.viewFromHash()));
    this.showView(this.viewFromHash());
  },

  /** Screen name in the URL, or 'live' when the hash is empty/invalid. */
  viewFromHash() {
    const name = window.location.hash.replace(/^#\/?/, '');
    return VIEWS.includes(name) ? name : 'live';
  },

  showView(name) {
    this.currentView = name;

    // Keep the URL in sync without stacking duplicate history entries
    // when the change came from hashchange itself.
    if (this.viewFromHash() !== name) window.location.hash = name;

    for (const button of $$('.nav__item')) {
      button.classList.toggle('is-active', button.dataset.view === name);
    }
    for (const section of $$('.view')) {
      section.classList.toggle('is-active', section.dataset.view === name);
    }

    this.updateViewHeader();

    // Settings and Calibration re-read tasks.yaml when opened, so they
    // reflect edits made on the other tab (or by hand in the file).
    if (name === 'settings') settingsView.loadTasks();
    if (name === 'calibration') calibrationView.loadTasks();
    if (name === 'employees') employeesView.loadEmployees();
    if (name === 'triggers') triggersView.load();
  },

  /** Title and subtitle of the header, for the active screen. */
  updateViewHeader() {
    $('#view-title').textContent = t(`nav.${this.currentView}`);
    $('#view-subtitle').textContent = t(`view.${this.currentView}.subtitle`);
  },

  // ------------------------------------------------------------------ //
  // Data that does not change while running
  // ------------------------------------------------------------------ //
  async loadStaticData() {
    try {
      const [system, taskTypes, triggerActionTypes] = await Promise.all([
        api.getSystem(), api.getTaskTypes(), api.getTriggerActionTypes(),
      ]);
      this.system = system;
      this.renderSystemStatus();
      settingsView.setTaskTypes(taskTypes);
      triggersView.setTaskTypes(taskTypes);
      triggersView.setActionTypes(triggerActionTypes);
    } catch (error) {
      toast(error.message, 'error');
    }
  },

  /** Sidebar footer. Kept in a method so it can be redrawn after a
   *  language change (the narrator's "off" label is translated). */
  renderSystemStatus() {
    if (!this.system) return;
    $('#status-device').textContent = this.system.device;
    $('#status-pipelines').textContent = this.system.pipeline_count;
    $('#status-llm').textContent = this.system.llm_enabled
      ? this.system.llm_model
      : t('status.narrator_off');
  },

  // ------------------------------------------------------------------ //
  // Polling
  // ------------------------------------------------------------------ //
  async poll() {
    try {
      const state = await api.getState();
      this.setConnected(true);

      liveView.render(state.cameras);
      this.renderAlerts(state.alerts);
      this.renderSummary(state.summary, state.narrator_enabled);

      // The camera <select> elements of the other screens are filled
      // once, on the first cycle — the camera list comes from
      // cameras.yaml and only changes when the application restarts.
      if (!this.camerasLoaded && state.cameras.length > 0) {
        this.camerasLoaded = true;
        calibrationView.setCameras(state.cameras);
        settingsView.setCameras(state.cameras);
        employeesView.setCameras(state.cameras);
        triggersView.setCameras(state.cameras);
      }

      // Pending trigger approvals only matter in "ask" mode and only
      // while that screen is open — triggersView.pollPending() itself
      // no-ops when mode is "auto", so this stays cheap otherwise.
      if (this.currentView === 'triggers') triggersView.pollPending();

      $('#status-cameras').textContent = state.cameras.filter((c) => c.connected).length
        + '/' + state.cameras.length;
    } catch {
      // Server down or restarting: mark it offline and try again on the
      // next cycle, without flooding the screen with toasts.
      this.setConnected(false);
    }
  },

  setConnected(online) {
    const dot = $('#status-dot');
    dot.className = `dot ${online ? 'is-online' : 'is-offline'}`;
    $('#status-conn').textContent = t(online ? 'status.connected' : 'status.disconnected');
  },

  // ------------------------------------------------------------------ //
  // Alerts panel
  // ------------------------------------------------------------------ //
  bindAlertsPanel() {
    for (const chip of $$('#alerts-filters .chip')) {
      chip.addEventListener('click', () => {
        this.alertFilter = chip.dataset.severity;
        for (const other of $$('#alerts-filters .chip')) {
          other.classList.toggle('is-active', other === chip);
        }
        this.renderAlerts(this.lastAlerts ?? []);
      });
    }

    $('#toggle-alerts').addEventListener('click', () => {
      $('.app-shell').classList.toggle('alerts-hidden');
    });
  },

  renderAlerts(alerts) {
    this.lastAlerts = alerts;

    const filtered = this.alertFilter === 'all'
      ? alerts
      : alerts.filter((alert) => alert.severity === this.alertFilter);

    // Most recent first — the backend returns them chronologically.
    const ordered = [...filtered].reverse();

    const list = $('#alerts-list');
    clear(list);
    setVisible($('#alerts-empty'), ordered.length === 0);

    for (const alert of ordered) {
      list.append(el('article', { class: `alert-item alert-item--${alert.severity}` },
        el('div', { class: 'alert-item__top' },
          el('span', { class: `badge badge--${alert.severity}` }, t(`severity.${alert.severity}`)),
          el('span', { class: 'alert-item__camera' }, alert.camera_id),
          el('time', {
            class: 'alert-item__time',
            title: formatTime(alert.timestamp),
          }, formatRelative(alert.timestamp)),
        ),
        el('p', { class: 'alert-item__message' }, alertMessage(alert)),
        el('p', { class: 'alert-item__task' }, `${alert.task_type} · ${alert.flag_id}`),
      ));
    }

    this.updateAlertBadge(alerts);
  },

  /** Red counter over the bell, with the total of retained alerts. */
  updateAlertBadge(alerts) {
    const badge = $('#alerts-count');
    badge.textContent = alerts.length > 99 ? '99+' : String(alerts.length);
    badge.hidden = alerts.length === 0;

    // A toast for each critical alert that arrived since the last cycle
    // — the panel may be hidden or out of sight.
    const fresh = alerts.filter((alert) => alert.timestamp > this.newestAlertSeen);

    if (this.alertsPrimed) {
      for (const alert of fresh.filter((alert) => alert.severity === 'critical')) {
        toast(`[${alert.camera_id}] ${alertMessage(alert)}`, 'error');
      }
    }

    for (const alert of alerts) {
      if (alert.timestamp > this.newestAlertSeen) this.newestAlertSeen = alert.timestamp;
    }
    this.alertsPrimed = true;
  },

  renderSummary(summary, narratorEnabled) {
    const card = $('#summary-card');
    setVisible(card, narratorEnabled);

    if (!narratorEnabled) return;
    $('#summary-text').textContent = summary || t('alerts.summary_waiting');
  },
};

/**
 * Text of an alert in the chosen language.
 *
 * The analyzers send `message_key` + `message_params` precisely so this
 * can be translated here; `message` (already rendered in English by the
 * backend) is the fallback for flags without a key.
 */
function alertMessage(alert) {
  if (alert.message_key) return t(alert.message_key, alert.message_params);
  return alert.message || alert.flag_id;
}

app.boot();
