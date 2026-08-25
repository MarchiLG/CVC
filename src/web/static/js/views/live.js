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
import { $, clear, el, formatCounts, setVisible } from '../ui.js';

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

    this.applyColumns();
  },

  /**
   * (Re)builds the grid when the camera list changes.
   * Called by the polling loop in app.js, but it only does real work
   * when the ids changed — rebuilding every second would reopen all the
   * streams and make the screen flicker.
   */
  render(cameras) {
    const changed =
      cameras.length !== this.cameras.length ||
      cameras.some((camera, index) => camera.id !== this.cameras[index]?.id);

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

      const card = el('article', { class: 'camera-card', dataset: { camera: camera.id } },
        el('header', { class: 'camera-card__header' },
          dot,
          el('span', { class: 'camera-card__name' }, camera.name),
          el('span', { class: 'camera-card__id' }, camera.id),
        ),
        video,
        footer,
      );

      this.grid.append(card);
      this.cards.set(camera.id, { card, img, dot, footer });
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
    }
    this.update(this.cameras);
  },
};
