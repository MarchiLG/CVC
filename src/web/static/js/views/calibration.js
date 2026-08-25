/**
 * views/calibration.js — the "Calibration" screen.
 *
 * Flow: pick a camera + task -> "Capture frame" freezes a snapshot on
 * the <canvas> -> each click marks a point -> "Save" writes the
 * geometry into config/tasks.yaml.
 *
 * THE IMPORTANT DETAIL is the coordinates. The canvas is created at the
 * frame's NATIVE resolution (e.g. 1920x1080) and merely SHRUNK by CSS to
 * fit the screen. A click arrives in screen coordinates, which have to
 * be converted back into frame pixels before going to the server — that
 * is what `toNativeCoords()` does. Without that conversion, the saved
 * zones would be offset from the real video.
 *
 * Validation (2 points for a line, 3+ for a zone, name required) happens
 * on the backend in config/calibration.py, the SAME module the Qt GUI
 * uses — here we only display whatever error comes back, already
 * translated by api.js.
 */

import { api } from '../api.js';
import { t } from '../i18n.js';
import { $, el, fillSelect, guard, setVisible, toast } from '../ui.js';

/** Drawing colors — they mirror the constants in vision/overlay.py. */
const POINT_COLOR = '#46d5c7';
const SHAPE_COLOR = '#f2545b';
const EXISTING_COLOR = 'rgba(240, 169, 43, 0.85)';

export const calibrationView = {
  points: [],          // clicked points, in NATIVE coordinates
  frameImage: null,    // Image() of the frozen snapshot
  tasks: [],           // tasks of the selected camera

  init() {
    this.cameraSelect = $('#calib-camera');
    this.taskSelect = $('#calib-task');
    this.zoneField = $('#calib-zone-field');
    this.zoneNameInput = $('#calib-zone-name');
    this.classField = $('#calib-class-field');
    this.expectedClassInput = $('#calib-expected-class');
    this.canvasWrap = $('#calib-canvas-wrap');
    this.canvas = $('#calib-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.hint = $('#calib-hint');
    this.saveButton = $('#calib-save');

    this.cameraSelect.addEventListener('change', () => this.loadTasks());
    this.taskSelect.addEventListener('change', () => this.onTaskChange());

    $('#calib-capture').addEventListener('click', () => this.captureFrame());
    $('#calib-undo').addEventListener('click', () => this.undoPoint());
    $('#calib-clear').addEventListener('click', () => this.clearPoints());
    this.saveButton.addEventListener('click', () => this.save());

    this.canvas.addEventListener('click', (event) => this.onCanvasClick(event));
  },

  /** Receives the camera list from app.js (once, at boot). */
  setCameras(cameras) {
    fillSelect(this.cameraSelect, cameras.map((camera) => ({
      value: camera.id,
      label: `${camera.name} (${camera.id})`,
    })));
    this.loadTasks();
  },

  get cameraId() { return this.cameraSelect.value; },

  /** Index of the selected task in tasks.yaml (not the select index). */
  get taskIndex() { return Number(this.taskSelect.value); },

  get task() { return this.tasks.find((task) => task.index === this.taskIndex) ?? null; },

  async loadTasks() {
    if (!this.cameraId) return;

    const tasks = await guard(api.getTasks(this.cameraId));
    if (!tasks) return;

    // Only tasks with geometry show up here — face_id, for instance,
    // has no line and no zone to draw.
    this.tasks = tasks.filter((task) => task.geometry !== null);

    fillSelect(this.taskSelect, this.tasks.map((task) => ({
      value: task.index,
      label: `${task.index}: ${task.type}`,
    })));

    this.onTaskChange();
  },

  /** Adapts the fields and hint text to the task's geometry kind. */
  onTaskChange() {
    this.clearPoints();
    const task = this.task;

    if (!task) {
      setVisible(this.zoneField, false);
      setVisible(this.classField, false);
      this.hint.textContent = this.tasks.length === 0
        ? t('calib.hint.no_tasks')
        : t('calib.hint.select_task');
      return;
    }

    const isZone = task.geometry === 'zone';
    setVisible(this.zoneField, isZone);
    setVisible(this.classField, task.type === 'missing_product');

    // Pre-loads the name/class of the first saved zone, so recalibrating
    // an existing zone REPLACES it instead of duplicating it.
    const firstZone = task.params?.zones?.[0];
    this.zoneNameInput.value = firstZone?.name ?? '';
    this.expectedClassInput.value = firstZone?.expected_class ?? '';

    this.hint.textContent = t(isZone ? 'calib.hint.zone' : 'calib.hint.line');
  },

  /**
   * Freezes the camera's current frame on the canvas.
   * Requests the snapshot WITHOUT overlay and at native resolution
   * (width=0) — the coordinates must match the real frame pixels.
   */
  captureFrame() {
    if (!this.cameraId) return;

    const image = new Image();

    image.onload = () => {
      this.frameImage = image;
      this.canvas.width = image.naturalWidth;
      this.canvas.height = image.naturalHeight;
      setVisible(this.canvasWrap, true);

      this.points = [];
      this.redraw();
      this.hint.textContent = t('calib.hint.captured', {
        width: image.naturalWidth,
        height: image.naturalHeight,
      });
    };

    image.onerror = () => toast(t('api.no_frame'), 'error');

    image.src = api.snapshotUrl(this.cameraId, { overlay: false, width: 0 });
  },

  /**
   * Converts a mouse click into FRAME coordinates.
   *
   * getBoundingClientRect() gives the canvas size ON SCREEN (already
   * shrunk by CSS); canvas.width/height give the native resolution. The
   * ratio between them is the scale factor.
   */
  toNativeCoords(event) {
    const rect = this.canvas.getBoundingClientRect();
    return [
      (event.clientX - rect.left) * (this.canvas.width / rect.width),
      (event.clientY - rect.top) * (this.canvas.height / rect.height),
    ];
  },

  onCanvasClick(event) {
    const task = this.task;
    if (!this.frameImage || !task) return;

    // A line takes exactly 2 points: the third click starts over, the
    // same behavior as the Qt GUI.
    if (task.geometry === 'line' && this.points.length >= 2) {
      this.points = [];
    }

    this.points.push(this.toNativeCoords(event));
    this.redraw();
  },

  undoPoint() {
    this.points.pop();
    this.redraw();
  },

  clearPoints() {
    this.points = [];
    this.redraw();
  },

  // ------------------------------------------------------------------ //
  // Drawing
  // ------------------------------------------------------------------ //

  /** Redraws everything from scratch: frame -> saved geometry -> new points. */
  redraw() {
    if (!this.frameImage) {
      this.updateSaveButton();
      return;
    }

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.ctx.drawImage(this.frameImage, 0, 0);

    this.drawExistingGeometry();
    this.drawCurrentShape();
    this.drawPoints();

    this.updateSaveButton();
  },

  /** Geometry already stored in tasks.yaml, in translucent amber — it
   *  serves as a reference for recalibrating without losing the old
   *  framing. */
  drawExistingGeometry() {
    const params = this.task?.params;
    if (!params) return;

    this.ctx.save();
    this.ctx.strokeStyle = EXISTING_COLOR;
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([8, 6]);

    if (params.counting_line?.p1 && params.counting_line?.p2) {
      const { p1, p2 } = params.counting_line;
      this.ctx.beginPath();
      this.ctx.moveTo(p1[0], p1[1]);
      this.ctx.lineTo(p2[0], p2[1]);
      this.ctx.stroke();
    }

    for (const zone of params.zones ?? []) {
      if (!zone.polygon || zone.polygon.length < 3) continue;
      this.ctx.beginPath();
      zone.polygon.forEach(([x, y], index) => {
        if (index === 0) this.ctx.moveTo(x, y); else this.ctx.lineTo(x, y);
      });
      this.ctx.closePath();
      this.ctx.stroke();

      if (zone.name) {
        this.ctx.setLineDash([]);
        this.ctx.fillStyle = EXISTING_COLOR;
        this.ctx.font = '16px sans-serif';
        this.ctx.fillText(zone.name, zone.polygon[0][0] + 6, zone.polygon[0][1] - 6);
        this.ctx.setLineDash([8, 6]);
      }
    }

    this.ctx.restore();
  },

  /** The line/polygon currently being drawn. */
  drawCurrentShape() {
    if (this.points.length < 2) return;

    this.ctx.save();
    this.ctx.strokeStyle = SHAPE_COLOR;
    this.ctx.fillStyle = 'rgba(242, 84, 91, 0.15)';
    this.ctx.lineWidth = 3;

    this.ctx.beginPath();
    this.points.forEach(([x, y], index) => {
      if (index === 0) this.ctx.moveTo(x, y); else this.ctx.lineTo(x, y);
    });

    if (this.task?.geometry === 'zone') {
      this.ctx.closePath();
      this.ctx.fill();
    }
    this.ctx.stroke();
    this.ctx.restore();
  },

  /** Numbered dots, so the vertex order can be checked at a glance. */
  drawPoints() {
    this.ctx.save();
    this.points.forEach(([x, y], index) => {
      this.ctx.beginPath();
      this.ctx.arc(x, y, 7, 0, Math.PI * 2);
      this.ctx.fillStyle = POINT_COLOR;
      this.ctx.fill();
      this.ctx.strokeStyle = '#06231f';
      this.ctx.lineWidth = 2;
      this.ctx.stroke();

      this.ctx.fillStyle = '#06231f';
      this.ctx.font = 'bold 11px sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText(String(index + 1), x, y);
    });
    this.ctx.restore();
  },

  /** "Save" only enables once the geometry has enough points. */
  updateSaveButton() {
    const geometry = this.task?.geometry;
    const enough =
      (geometry === 'line' && this.points.length === 2) ||
      (geometry === 'zone' && this.points.length >= 3);

    this.saveButton.disabled = !enough;
    this.saveButton.textContent = enough
      ? t('calib.save_points', { count: this.points.length })
      : t('calib.save');
  },

  // ------------------------------------------------------------------ //
  async save() {
    const task = this.task;
    if (!task) return;

    const result = await guard(api.saveGeometry(this.cameraId, task.index, {
      points: this.points,
      zoneName: this.zoneNameInput.value,
      expectedClass: this.expectedClassInput.value,
    }));
    if (!result) return;

    toast(t('calib.saved'), 'success');

    // Reload the tasks so the just-saved geometry already shows as
    // "existing" (dashed) on the next redraw.
    await this.loadTasks();
    this.redraw();

    // Apply it to the running pipeline, without restarting.
    await guard(api.reload());
  },

  /** Redraws the language-dependent texts after a language change. */
  retranslate() {
    this.onTaskChange();
  },
};
