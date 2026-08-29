/**
 * views/settings.js — the "Settings" screen.
 *
 * Edits each camera's tasks in config/tasks.yaml: add, remove, adjust
 * detect_fps / required_ppe and configure the flags (enabled, severity,
 * notification channels).
 *
 * Every task becomes a "task-card" built by `renderTask()`. Changes are
 * NOT saved as you type: each card has its own "Save" button, which
 * fires two calls — one for the task fields and one for the flags.
 *
 * After saving, `api.reload()` rebuilds the inference pipelines with the
 * new YAML, so the change takes effect immediately (the Qt GUI only
 * writes the file; the difference is documented in the README).
 */

import { api } from '../api.js';
import { t } from '../i18n.js';
import { $, clear, el, fillSelect, guard, setVisible, toast } from '../ui.js';

const SEVERITIES = ['info', 'warning', 'critical'];

/** Channels accepted by FlagManager (see src/notify/flag_manager.py). */
const NOTIFY_CHANNELS = ['log', 'desktop', 'db'];

export const settingsView = {
  taskTypes: [],
  modelsByKind: {},

  init() {
    this.cameraSelect = $('#settings-camera');
    this.newTypeSelect = $('#settings-new-type');
    this.list = $('#settings-tasks');
    this.empty = $('#settings-empty');

    this.cameraSelect.addEventListener('change', () => this.loadTasks());
    $('#settings-add').addEventListener('click', () => this.addTask());
    $('#settings-apply').addEventListener('click', () => this.applyNow());
  },

  setCameras(cameras) {
    fillSelect(this.cameraSelect, cameras.map((camera) => ({
      value: camera.id,
      label: `${camera.name} (${camera.id})`,
    })));
    this.loadTasks();
  },

  setTaskTypes(types) {
    this.taskTypes = types;
    // Task types are identifiers used in tasks.yaml, not prose — they
    // stay the same in every language.
    fillSelect(this.newTypeSelect, types.map((type) => ({
      value: type.type,
      label: type.type,
    })));
  },

  get cameraId() { return this.cameraSelect.value; },

  async loadTasks() {
    if (!this.cameraId) return;

    const tasks = await guard(api.getTasks(this.cameraId));
    if (!tasks) return;

    await this.loadModelsFor(tasks);

    clear(this.list);
    setVisible(this.empty, tasks.length === 0);

    for (const task of tasks) {
      this.list.append(this.renderTask(task));
    }
  },

  /** Fetches models/<kind>/ for every distinct model_kind these tasks
   *  need (skipping "none" — those tasks manage their own model and get
   *  no picker), caching each kind's list across calls. */
  async loadModelsFor(tasks) {
    const kinds = new Set(tasks.map((task) => task.model_kind).filter((kind) => kind && kind !== 'none'));
    for (const kind of kinds) {
      if (this.modelsByKind[kind]) continue;
      const result = await guard(api.getModels(kind));
      this.modelsByKind[kind] = result?.[kind] ?? [];
    }
  },

  // ------------------------------------------------------------------ //
  // Building a task-card
  // ------------------------------------------------------------------ //

  /**
   * Builds one task's card.
   *
   * The inputs are kept in `refs` so the save handler can read their
   * values on click — no mirrored state, no re-render on every
   * keystroke.
   */
  renderTask(task) {
    const refs = {};

    const fpsInput = el('input', {
      type: 'number', class: 'input', min: '0.1', max: '30', step: '0.1',
      value: task.detect_fps,
    });
    refs.detectFps = fpsInput;

    const body = el('div', { class: 'task-card__body' },
      el('div', { class: 'field' },
        el('label', {}, t('settings.detect_fps')),
        fpsInput,
        el('span', { class: 'panel__hint', style: 'margin:0' }, t('settings.detect_fps_hint')),
      ),
    );

    if (task.model_kind && task.model_kind !== 'none') {
      const available = this.modelsByKind[task.model_kind] ?? [];
      const options = [
        { value: '', label: t('settings.model_placeholder') },
        ...available.map((path) => ({ value: path, label: path })),
      ];
      const missing = task.model && !available.includes(task.model);
      if (missing) {
        options.push({ value: task.model, label: `${task.model} (${t('settings.model_missing')})` });
      }

      const modelSelect = el('select', { class: 'input' });
      fillSelect(modelSelect, options);
      modelSelect.value = task.model ?? '';
      refs.model = modelSelect;

      body.append(el('div', { class: 'field' },
        el('label', {}, t('settings.model')),
        modelSelect,
        el('span', { class: 'panel__hint', style: 'margin:0' }, t('settings.model_hint')),
        missing && el('div', { class: 'notice notice--warning' },
          t('settings.model_missing_warning', { path: task.model })),
      ));
    }

    // required_ppe only exists on ppe_compliance — the dedicated editor
    // shows up for that type alone; the remaining params land in the
    // read-only preview further down.
    if (task.type === 'ppe_compliance') {
      const ppeInput = el('input', {
        type: 'text', class: 'input',
        value: (task.params?.required_ppe ?? []).join(', '),
        placeholder: t('settings.required_ppe_placeholder'),
      });
      refs.requiredPpe = ppeInput;

      body.append(el('div', { class: 'field' },
        el('label', {}, t('settings.required_ppe')),
        ppeInput,
        el('span', { class: 'panel__hint', style: 'margin:0' }, t('settings.required_ppe_hint')),
      ));
    }

    // Geometry (line/zone) is read-only here: it is edited on the
    // Calibration screen, which draws over the video.
    //
    // A task with geometry but WITHOUT calibration does not run: the
    // TaskAnalyzer is never even constructed (the builder logs the
    // reason and leaves the camera without a pipeline). That is why the
    // warning here is prominent rather than just one more line in the
    // preview.
    if (task.geometry && !this.hasGeometry(task)) {
      body.append(el('div', { class: 'notice notice--warning' },
        t(`settings.not_calibrated.${task.geometry}`)));
    } else {
      const geometrySummary = this.describeGeometry(task);
      if (geometrySummary) {
        body.append(el('pre', { class: 'params-preview' }, geometrySummary));
      }
    }

    body.append(this.renderFlags(task, refs));

    return el('article', { class: 'task-card', dataset: { index: task.index } },
      el('header', { class: 'task-card__header' },
        el('span', { class: 'task-card__type' }, task.type),
        task.geometry && el('span', { class: 'badge badge--accent' },
          t(`settings.geometry.${task.geometry}`)),
        el('span', { class: 'task-card__spacer' }),
        el('span', { class: 'badge' }, `#${task.index}`),
        el('button', {
          class: 'btn btn--danger btn--sm',
          onClick: () => this.removeTask(task),
        }, t('settings.remove')),
      ),
      body,
      el('footer', { class: 'task-card__footer' },
        el('span', { class: 'task-card__note' }, t('settings.save_note')),
        el('button', {
          class: 'btn btn--primary btn--sm',
          onClick: (event) => this.saveTask(task, refs, event.currentTarget),
        }, t('settings.save')),
      ),
    );
  },

  /** Does the task already have the geometry its type requires? */
  hasGeometry(task) {
    const params = task.params ?? {};
    if (task.geometry === 'line') return Boolean(params.counting_line?.p1);
    if (task.geometry === 'zone') return (params.zones ?? []).length > 0;
    return true;
  },

  /**
   * Textual summary of the calibrated geometry, for the card.
   * Deliberately not translated: these are the literal keys and values
   * from tasks.yaml, shown as a technical preview.
   */
  describeGeometry(task) {
    const params = task.params ?? {};
    const lines = [];

    if (params.counting_line?.p1) {
      const { p1, p2 } = params.counting_line;
      lines.push(`counting_line: [${p1}] -> [${p2}]`);
    }
    for (const zone of params.zones ?? []) {
      const vertices = zone.polygon?.length ?? 0;
      const expected = zone.expected_class ? `, expects "${zone.expected_class}"` : '';
      lines.push(`zone "${zone.name}": ${vertices} vertices${expected}`);
    }

    return lines.join('\n');
  },

  /** Flags block: one row per flag configured on the task. */
  renderFlags(task, refs) {
    refs.flags = [];

    const rows = task.flags.map((flag) => {
      const enabled = el('input', { type: 'checkbox', checked: flag.enabled });
      const severity = el('select', { class: 'input input--sm' },
        ...SEVERITIES.map((value) => el('option', { value, selected: value === flag.severity },
          t(`severity.${value}`))));
      const notify = el('input', {
        type: 'text', class: 'input input--sm',
        value: flag.notify.join(', '),
        placeholder: NOTIFY_CHANNELS.join(', '),
      });

      refs.flags.push({ id: flag.id, enabled, severity, notify });

      return el('div', { class: 'flag-row' },
        el('span', { class: 'flag-row__id' }, flag.id),
        el('label', { class: 'switch' },
          enabled,
          el('span', { class: 'switch__track' }, el('span', { class: 'switch__thumb' })),
          el('span', {}, t('settings.flag_active')),
        ),
        severity,
        notify,
      );
    });

    return el('div', { class: 'flag-list' },
      el('span', { class: 'flag-list__title' }, t('settings.flags', { count: task.flags.length })),
      ...rows,
      task.flags.length === 0 && el('span', { class: 'panel__hint', style: 'margin:0' },
        t('settings.no_flags')),
    );
  },

  // ------------------------------------------------------------------ //
  // Actions
  // ------------------------------------------------------------------ //

  async saveTask(task, refs, button) {
    button.disabled = true;
    try {
      // 1) Task fields. Existing params are preserved and only
      //    required_ppe is overwritten, so the geometry calibrated on
      //    the other screen is not wiped out.
      const patch = { detect_fps: Number(refs.detectFps.value) };

      if (refs.requiredPpe) {
        patch.params = {
          ...task.params,
          required_ppe: splitList(refs.requiredPpe.value),
        };
      }

      // Empty string ("device default") clears the model: field in
      // tasks.yaml, falling back to vision.model_size_override/device
      // defaults — see config/writer.py's set_task_model().
      if (refs.model) {
        patch.model = refs.model.value;
      }

      const saved = await guard(api.updateTask(this.cameraId, task.index, patch));
      if (!saved) return;

      // 2) Flags, when there are any.
      if (refs.flags.length > 0) {
        const flags = refs.flags.map((ref) => ({
          id: ref.id,
          enabled: ref.enabled.checked,
          severity: ref.severity.value,
          notify: splitList(ref.notify.value),
        }));
        if (!await guard(api.saveFlags(this.cameraId, task.index, flags))) return;
      }

      await guard(api.reload());
      toast(t('settings.saved', { type: task.type }), 'success');
      await this.loadTasks();
    } finally {
      button.disabled = false;
    }
  },

  async addTask() {
    const type = this.newTypeSelect.value;
    if (!type || !this.cameraId) return;

    if (!await guard(api.addTask(this.cameraId, type))) return;

    toast(t('settings.added', { type }), 'success');
    await this.loadTasks();
  },

  async removeTask(task) {
    if (!confirm(t('settings.confirm_remove', { type: task.type, index: task.index }))) return;

    if (!await guard(api.deleteTask(this.cameraId, task.index))) return;

    await guard(api.reload());
    toast(t('settings.removed'), 'success');
    await this.loadTasks();
  },

  /** Reloads the pipelines without saving anything — handy after
   *  editing tasks.yaml by hand in a text editor. */
  async applyNow() {
    const result = await guard(api.reload());
    if (!result) return;
    toast(t('settings.reloaded', { count: result.pipeline_count }), 'success');
    await this.loadTasks();
  },

  /** Rebuilds the cards after a language change. */
  retranslate() {
    this.loadTasks();
  },
};

/** "log, desktop" -> ["log", "desktop"], ignoring spaces and blanks. */
function splitList(value) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}
