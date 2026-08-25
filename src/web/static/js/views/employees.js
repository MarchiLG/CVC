/**
 * views/employees.js — the "Employees" screen.
 *
 * Enrollment for the `face_id` task: captures a face (from a camera or
 * an upload) and sends it to the backend, which extracts the face
 * embedding with InsightFace and stores it in SQLite. THE PHOTO ITSELF
 * IS NOT STORED — only the vector.
 *
 * Mirrors the gui_qt/widgets/employee_enrollment.py screen of the
 * desktop GUI; both write to the same database (data/app.db), so an
 * enrollment made here shows up there and vice versa.
 */

import { api } from '../api.js';
import { t } from '../i18n.js';
import { $, clear, el, fillSelect, guard, initials, setVisible, toast } from '../ui.js';

export const employeesView = {
  /** Source of the current image: a File (upload) or a camera id. */
  pendingFile: null,
  pendingCameraId: null,

  init() {
    this.cameraSelect = $('#emp-camera');
    this.fileInput = $('#emp-file');
    this.nameInput = $('#emp-name');
    this.previewImg = $('#emp-preview-img');
    this.previewPlaceholder = $('.preview__placeholder', $('#emp-preview'));
    this.list = $('#emp-list');
    this.empty = $('#emp-empty');

    $('#emp-capture').addEventListener('click', () => this.captureFromCamera());
    $('#emp-enroll').addEventListener('click', () => this.enroll());
    this.fileInput.addEventListener('change', () => this.onFileSelected());

    this.previewImg.alt = t('emp.preview_alt');
    this.loadEmployees();
  },

  setCameras(cameras) {
    fillSelect(this.cameraSelect, cameras.map((camera) => ({
      value: camera.id,
      label: `${camera.name} (${camera.id})`,
    })));
  },

  // ------------------------------------------------------------------ //
  // Choosing the image
  // ------------------------------------------------------------------ //

  /**
   * Freezes the camera's current frame in the preview.
   *
   * The image shown is only a preview: at enrollment time the backend
   * reads the camera's CURRENT frame again. To make sure the enrolled
   * face is the one on screen, enroll right after capturing.
   */
  captureFromCamera() {
    const cameraId = this.cameraSelect.value;
    if (!cameraId) return;

    const url = api.snapshotUrl(cameraId, { overlay: false, width: 640 });

    const image = new Image();
    image.onload = () => {
      this.showPreview(url);
      this.pendingCameraId = cameraId;
      this.pendingFile = null;
      this.fileInput.value = '';
      toast(t('emp.captured'), 'success');
    };
    image.onerror = () => toast(t('api.no_frame'), 'error');
    image.src = url;
  },

  /** Reads the chosen file and shows it in the preview. */
  onFileSelected() {
    const file = this.fileInput.files?.[0];
    if (!file) return;

    this.pendingFile = file;
    this.pendingCameraId = null;
    this.showPreview(URL.createObjectURL(file));
  },

  showPreview(src) {
    this.previewImg.src = src;
    setVisible(this.previewImg, true);
    setVisible(this.previewPlaceholder, false);
  },

  clearPreview() {
    this.previewImg.src = '';
    setVisible(this.previewImg, false);
    setVisible(this.previewPlaceholder, true);
    this.pendingFile = null;
    this.pendingCameraId = null;
    this.fileInput.value = '';
  },

  // ------------------------------------------------------------------ //
  // Enrollment
  // ------------------------------------------------------------------ //
  async enroll() {
    const name = this.nameInput.value.trim();
    if (!name) {
      toast(t('emp.name_required'), 'error');
      return;
    }
    if (!this.pendingFile && !this.pendingCameraId) {
      toast(t('emp.image_required'), 'error');
      return;
    }

    const result = await guard(api.enrollEmployee({
      name,
      cameraId: this.pendingCameraId,
      file: this.pendingFile,
    }));
    if (!result) return;

    toast(t('emp.enrolled', { name: result.name }), 'success');
    this.nameInput.value = '';
    this.clearPreview();
    await this.loadEmployees();
  },

  async loadEmployees() {
    const employees = await guard(api.getEmployees());
    if (!employees) return;

    clear(this.list);
    setVisible(this.empty, employees.length === 0);

    for (const employee of employees) {
      this.list.append(el('div', { class: 'employee-row' },
        el('span', { class: 'employee-row__avatar' }, initials(employee.name)),
        el('span', { class: 'employee-row__name' }, employee.name),
        el('span', { class: 'employee-row__meta' },
          `#${employee.id} · ${t('emp.faces', { count: employee.embedding_count })}`),
      ));
    }
  },

  /** Rebuilds the list after a language change. */
  retranslate() {
    this.previewImg.alt = t('emp.preview_alt');
    this.loadEmployees();
  },
};
