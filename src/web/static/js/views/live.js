/**
 * views/live.js — the "Live" screen: a grid with every camera.
 *
 * How the video works: each card holds an <img> whose src points at
 * /api/cameras/<id>/stream. That endpoint returns MJPEG
 * (multipart/x-mixed-replace), a format the browser understands
 * natively — it keeps the connection open and swaps the image on every
 * frame received. There is no WebSocket, no player and no <video>.
 *
 * Practical consequence: changing quality/overlay means changing the
 * <img> src, which reopens the connection. That is why the src is only
 * rewritten when the parameters ACTUALLY change (see `applyStreamSrc`).
 */

import { api } from '../api.js';
import { t } from '../i18n.js';
import { $, clear, el, formatCounts, guard, setVisible, toast } from '../ui.js';

/** Presets of the quality <select>: "width:jpegQuality:fps". */
function parseQuality(value) {
  const [width, quality, fps] = value.split(':').map(Number);
  return { width, quality, fps };
}

export const liveView = {
  /** @type {Map<string, {card: HTMLElement, img: HTMLImageElement, dot: HTMLElement, footer: HTMLElement}>} */
  cards: new Map(),
  cameras: [],

  /** Called once, when the application boots. */
  init() {
    this.grid = $('#live-grid');
    this.empty = $('#live-empty');
    this.columnsSelect = $('#live-columns');
    this.qualitySelect = $('#live-quality');
    this.overlayToggle = $('#live-overlay');

    this.columnsSelect.addEventListener('change', () => this.applyColumns());

    // Quality and overlay change the stream URL -> recreate the <img>.
    this.qualitySelect.addEventListener('change', () => this.refreshStreams());
    this.overlayToggle.addEventListener('change', () => this.refreshStreams());

    this.initAddCameraPanel();
    this.applyColumns();
  },

  /**
   * (Re)builds the grid when the camera list changes.
   * Called by the polling loop in app.js, but it only does real work
   * when the ids/names/hosts changed — rebuilding every second would
   * reopen all the streams and make the screen flicker.
   */
  render(cameras) {
    const changed =
      cameras.length !== this.cameras.length ||
      cameras.some((camera, index) => {
        const previous = this.cameras[index];
        return !previous || camera.id !== previous.id
          || camera.name !== previous.name || camera.host !== previous.host;
      });

    if (changed) {
      this.cameras = cameras;
      this.build(cameras);
    }

    this.update(cameras);
  },

  build(cameras) {
    clear(this.grid);
    this.cards.clear();

    setVisible(this.empty, cameras.length === 0);

    for (const camera of cameras) {
      const dot = el('span', { class: 'live-dot' });
      const img = el('img', {
        alt: t('live.video_alt', { name: camera.name }),
        loading: 'lazy',
      });
      const footer = el('div', { class: 'camera-card__footer' });

      const video = el('div', {
        class: 'camera-card__video',
        title: t('live.expand'),
        onClick: () => this.openLightbox(camera),
      }, img);

      // The camera's own web configuration page — deliberately subtle
      // (faint, no blue "link" color) so it reads as metadata next to
      // the name rather than as a call to action.
      const hostLink = camera.host
        ? el('a', {
            class: 'camera-card__host',
            href: `http://${camera.host}`,
            target: '_blank',
            rel: 'noopener noreferrer',
            title: t('live.host_link_title', { host: camera.host }),
            onClick: (event) => event.stopPropagation(),
          }, camera.host)
        : null;

      const cog = el('button', {
        type: 'button',
        class: 'btn btn--ghost camera-card__cog',
        title: t('live.camera_settings'),
        onClick: (event) => { event.stopPropagation(); this.toggleSettings(camera); },
      }, '⚙');

      const settingsPanel = el('div', { class: 'camera-settings-panel', hidden: true });

      const card = el('article', { class: 'camera-card', dataset: { camera: camera.id } },
        el('header', { class: 'camera-card__header' },
          dot,
          el('div', { class: 'camera-card__title' },
            el('span', { class: 'camera-card__name' }, camera.name),
            hostLink,
          ),
          cog,
          el('span', { class: 'camera-card__id' }, camera.id),
        ),
        video,
        footer,
        settingsPanel,
      );

      this.grid.append(card);
      this.cards.set(camera.id, { card, img, dot, footer, hostLink, settingsPanel });
      this.applyStreamSrc(camera.id, img);
    }
  },

  /** Refreshes only what changes each cycle: status and object counts. */
  update(cameras) {
    for (const camera of cameras) {
      const parts = this.cards.get(camera.id);
      if (!parts) continue;

      parts.dot.className = `live-dot ${camera.connected ? 'is-live' : 'is-down'}`;
      parts.dot.title = t(camera.connected ? 'live.connected' : 'live.waiting');

      clear(parts.footer);
      parts.footer.append(
        el('span', {}, t(camera.connected ? 'live.streaming' : 'live.waiting')),
      );

      if (!camera.has_pipeline) {
        // With no task in tasks.yaml the camera shows up but nothing is
        // detected — saying so avoids the impression that it broke.
        parts.footer.append(el('span', { class: 'badge' }, t('live.no_tasks')));
      } else if (camera.track_count > 0) {
        parts.footer.append(
          el('span', { class: 'badge badge--accent' }, t('live.tracked', { count: camera.track_count })),
          el('span', {}, formatCounts(camera.class_counts)),
        );
      }
    }
  },

  /** Builds the stream URL from the toolbar controls. */
  applyStreamSrc(cameraId, img) {
    const { width, quality, fps } = parseQuality(this.qualitySelect.value);
    const overlay = this.overlayToggle.checked;

    // The boxes are drawn on the SERVER (vision/overlay.py), not in the
    // browser — turning the switch off asks for a stream without the
    // overlay, which also saves a little backend CPU.
    const src = api.streamUrl(cameraId, { width, quality, fps, overlay });

    if (img.dataset.src !== src) {
      img.dataset.src = src;
      img.src = src;
    }
  },

  /** Reopens every stream (after a quality/overlay change). */
  refreshStreams() {
    for (const [cameraId, parts] of this.cards) {
      this.applyStreamSrc(cameraId, parts.img);
    }
  },

  /** Fixed number of columns, or `auto` (as many as fit). */
  applyColumns() {
    const value = this.columnsSelect.value;
    this.grid.style.gridTemplateColumns = value === 'auto'
      ? 'repeat(auto-fit, minmax(380px, 1fr))'
      : `repeat(${value}, minmax(0, 1fr))`;
  },

  /** Opens one camera full screen, at high quality. */
  openLightbox(camera) {
    const img = el('img', {
      src: api.streamUrl(camera.id, { width: 1920, quality: 88, fps: 20 }),
      alt: t('live.zoom_alt', { name: camera.name }),
    });

    const close = () => {
      img.src = '';   // ends the MJPEG connection on close
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    };

    const onKey = (event) => { if (event.key === 'Escape') close(); };

    const overlay = el('div', { class: 'lightbox', onClick: close },
      el('div', { class: 'lightbox__caption' }, t('live.close_hint', { name: camera.name })),
      img,
    );

    document.body.append(overlay);
    document.addEventListener('keydown', onKey);
  },

  // ------------------------------------------------------------------ //
  // Per-camera settings (the cog button): edit its connection details
  // or delete it from cameras.yaml. There is no separate login for
  // this — it lives behind the same encrypted-vault password the whole
  // application already asked for at startup (see src/security/
  // env_vault.py), so opening it just fetches and shows what is
  // already in .env.
  // ------------------------------------------------------------------ //
  async toggleSettings(camera) {
    const parts = this.cards.get(camera.id);
    if (!parts) return;

    const panel = parts.settingsPanel;
    if (!panel.hidden) {
      setVisible(panel, false);
      return;
    }

    clear(panel);
    setVisible(panel, true);

    const detail = await guard(api.getCamera(camera.id));
    if (!detail) {
      setVisible(panel, false);
      return;
    }

    clear(panel);
    panel.append(this.renderSettingsForm(camera.id, detail));
  },

  renderSettingsForm(cameraId, detail) {
    const field = (label, input) => el('label', { class: 'camera-settings-panel__field' },
      el('span', {}, label), input);

    const nameInput = el('input', { class: 'input input--sm', value: detail.name });
    const protocolSelect = el('select', { class: 'input input--sm' },
      ...['rtsp', 'http', 'https'].map((protocol) =>
        el('option', { value: protocol, selected: protocol === detail.protocol }, protocol.toUpperCase())),
    );
    const hostInput = el('input', { class: 'input input--sm', value: detail.host });
    const portInput = el('input', {
      class: 'input input--sm', type: 'number', min: '1', max: '65535',
      value: detail.port ?? '',
    });
    const pathInput = el('input', { class: 'input input--sm', value: detail.path ?? '' });
    const usernameInput = el('input', { class: 'input input--sm', value: detail.username ?? '', autocomplete: 'off' });
    const passwordInput = el('input', {
      class: 'input input--sm', type: 'password', value: detail.password ?? '', autocomplete: 'new-password',
    });
    const enabledInput = el('input', { type: 'checkbox', checked: detail.enabled });

    const saveBtn = el('button', { type: 'button', class: 'btn btn--sm btn--primary' }, t('live.camera_settings.save'));
    const deleteBtn = el('button', { type: 'button', class: 'btn btn--sm btn--danger' }, t('live.camera_settings.delete'));

    saveBtn.addEventListener('click', () => this.saveCameraSettings(cameraId, {
      name: nameInput.value.trim(),
      protocol: protocolSelect.value,
      host: hostInput.value.trim(),
      port: portInput.value ? Number(portInput.value) : null,
      path: pathInput.value,
      username: usernameInput.value,
      password: passwordInput.value,
      enabled: enabledInput.checked,
    }));

    deleteBtn.addEventListener('click', () => this.deleteCamera(cameraId, detail.name));

    return el('div', { class: 'camera-settings-panel__form' },
      el('h4', { class: 'camera-settings-panel__title' }, t('live.camera_settings.title', { name: detail.name })),
      el('div', { class: 'camera-settings-panel__grid' },
        field(t('live.add_camera.name'), nameInput),
        field(t('live.add_camera.protocol'), protocolSelect),
        field(t('live.add_camera.host'), hostInput),
        field(t('live.add_camera.port'), portInput),
        field(t('live.add_camera.username'), usernameInput),
        field(t('live.add_camera.password'), passwordInput),
        el('label', { class: 'camera-settings-panel__field camera-settings-panel__field--wide' },
          el('span', {}, t('live.add_camera.path')), pathInput),
      ),
      el('label', { class: 'switch' },
        enabledInput,
        el('span', { class: 'switch__track' }, el('span', { class: 'switch__thumb' })),
        t('live.add_camera.enabled'),
      ),
      el('div', { class: 'camera-settings-panel__actions' }, deleteBtn, saveBtn),
    );
  },

  async saveCameraSettings(cameraId, payload) {
    const result = await guard(api.updateCamera(cameraId, payload));
    if (!result) return;

    toast(t('live.camera_settings.saved', { name: result.name }), 'success');
    const parts = this.cards.get(cameraId);
    if (parts) setVisible(parts.settingsPanel, false);
  },

  async deleteCamera(cameraId, name) {
    if (!window.confirm(t('live.camera_settings.confirm_delete', { name }))) return;

    const result = await guard(api.deleteCamera(cameraId));
    if (!result) return;

    toast(t('live.camera_settings.deleted', { name }), 'success');
  },

  // ------------------------------------------------------------------ //
  // "Add camera" panel, toggled by #live-add-camera-btn. The connection
  // string is assembled server-side (POST /api/cameras) from the
  // individual fields below, then written to cameras.yaml + the
  // encrypted .env vault.
  // ------------------------------------------------------------------ //
  initAddCameraPanel() {
    this.addCameraBtn = $('#live-add-camera-btn');
    this.addCameraPanel = $('#live-add-camera-panel');

    this.addCameraBtn.addEventListener('click', () => {
      setVisible(this.addCameraPanel, this.addCameraPanel.hidden);
    });
    $('#live-add-camera-cancel').addEventListener('click', () => {
      this.addCameraPanel.reset();
      setVisible(this.addCameraPanel, false);
    });
    this.addCameraPanel.addEventListener('submit', (event) => {
      event.preventDefault();
      this.submitNewCamera();
    });
  },

  async submitNewCamera() {
    const name = $('#cam-new-name').value.trim();
    const host = $('#cam-new-host').value.trim();
    if (!name || !host) return;

    const payload = {
      id: $('#cam-new-id').value.trim() || null,
      name,
      protocol: $('#cam-new-protocol').value,
      host,
      port: $('#cam-new-port').value ? Number($('#cam-new-port').value) : null,
      path: $('#cam-new-path').value,
      username: $('#cam-new-username').value,
      password: $('#cam-new-password').value,
      enabled: $('#cam-new-enabled').checked,
    };

    const result = await guard(api.addCamera(payload));
    if (!result) return;

    toast(t('live.add_camera.added', { name: result.name }), 'success');
    this.addCameraPanel.reset();
    setVisible(this.addCameraPanel, false);
  },

  /** Closes every stream — called when the browser tab goes away. */
  suspend() {
    for (const parts of this.cards.values()) {
      parts.img.src = '';
      // Clear the URL cache so resume() reassigns the src — without
      // this, applyStreamSrc() would think nothing changed and the
      // image would stay blank.
      delete parts.img.dataset.src;
    }
  },

  /** Reopens the streams when the tab comes back. */
  resume() {
    this.refreshStreams();
  },

  /**
   * Redraws the labels after a language change. The <img> elements are
   * left untouched on purpose: recreating them would needlessly reopen
   * every video connection.
   */
  retranslate() {
    for (const camera of this.cameras) {
      const parts = this.cards.get(camera.id);
      if (!parts) continue;
      parts.img.alt = t('live.video_alt', { name: camera.name });
      parts.card.querySelector('.camera-card__video').title = t('live.expand');
      if (parts.hostLink) parts.hostLink.title = t('live.host_link_title', { host: camera.host });
      // Closed rather than rebuilt in the new language: it is JS-built
      // from a fresh fetch each time it opens (see toggleSettings), so
      // reopening it already shows the right strings.
      setVisible(parts.settingsPanel, false);
    }
    this.update(this.cameras);
  },
};
