/**
 * views/triggers.js — the "Triggers" screen.
 *
 * Edits config/Triggers.yaml: the global ask/auto mode toggle, and
 * condition -> action rules that fire on alerts and drive external IO
 * devices (MQTT, Modbus TCP, HTTP webhook). Mirrors views/settings.js's
 * shape closely — one "rule-card" per rule, no live re-render on
 * keystroke, an explicit Save button per card — plus a pending-approvals
 * list only meaningful in "ask" mode.
 */

import { api } from '../api.js';
import { t } from '../i18n.js';
import { $, clear, el, fillSelect, guard, setVisible, toast } from '../ui.js';

const SEVERITIES = ['info', 'warning', 'critical'];

export const triggersView = {
  taskTypes: [],
  cameras: [],
  actionTypes: [],
  mode: 'ask',

  init() {
    this.modeToggle = $('#triggers-mode-toggle');
    this.modeLabel = $('#triggers-mode-label');
    this.newIdInput = $('#triggers-new-id');
    this.rulesList = $('#triggers-rules');
    this.rulesEmpty = $('#triggers-empty');
    this.pendingList = $('#triggers-pending');
    this.pendingEmpty = $('#triggers-pending-empty');

    this.modeToggle.addEventListener('change', () => this.setMode(this.modeToggle.checked ? 'auto' : 'ask'));
    $('#triggers-add').addEventListener('click', () => this.addRule());
  },

  setTaskTypes(types) {
    this.taskTypes = types;
  },

  setCameras(cameras) {
    this.cameras = cameras;
  },

  setActionTypes(types) {
    this.actionTypes = types;
  },

  /** Full reload: mode + rules — called when the screen is opened. */
  async load() {
    const [mode, rules] = await Promise.all([
      guard(api.getTriggerMode()),
      guard(api.getTriggers()),
    ]);

    if (mode) this.applyMode(mode.mode);
    if (rules) {
      clear(this.rulesList);
      setVisible(this.rulesEmpty, rules.length === 0);
      for (const rule of rules) this.rulesList.append(this.renderRule(rule));
    }

    await this.pollPending();
  },

  applyMode(mode) {
    this.mode = mode;
    this.modeToggle.checked = mode === 'auto';
    this.modeLabel.textContent = t(`triggers.mode.${mode}`);
  },

  async setMode(mode) {
    if (!await guard(api.setTriggerMode(mode))) {
      this.applyMode(this.mode);  // revert the toggle on failure
      return;
    }
    await guard(api.reloadTriggers());
    this.applyMode(mode);
    toast(t('triggers.mode_saved', { mode: t(`triggers.mode.${mode}`) }), 'success');
    await this.pollPending();
  },

  /** Only meaningful in "ask" mode — a no-op otherwise, so app.js can
   *  call this on every poll tick while this screen is active without
   *  hitting the backend needlessly in "auto" mode. */
  async pollPending() {
    if (this.mode !== 'ask') {
      clear(this.pendingList);
      setVisible(this.pendingEmpty, true);
      return;
    }

    const pending = await guard(api.getPendingTriggers());
    if (!pending) return;

    clear(this.pendingList);
    setVisible(this.pendingEmpty, pending.length === 0);
    for (const item of pending) this.pendingList.append(this.renderPending(item));
  },

  // ------------------------------------------------------------------ //
  // Rule cards
  // ------------------------------------------------------------------ //
  renderRule(rule) {
    const refs = { actions: [] };

    const enabledInput = el('input', { type: 'checkbox', checked: rule.enabled });
    refs.enabled = enabledInput;

    const taskTypeSelect = el('select', { class: 'input input--sm' });
    fillSelect(taskTypeSelect, [
      { value: '', label: t('triggers.any') },
      ...this.taskTypes.map((type) => ({ value: type.type, label: type.type })),
    ]);
    taskTypeSelect.value = rule.condition.task_type ?? '';
    refs.taskType = taskTypeSelect;

    const flagIdInput = el('input', {
      type: 'text', class: 'input input--sm',
      value: rule.condition.flag_id ?? '', placeholder: t('triggers.condition.flag_id_placeholder'),
    });
    refs.flagId = flagIdInput;

    const cameraSelect = el('select', { class: 'input input--sm' });
    fillSelect(cameraSelect, [
      { value: '', label: t('triggers.any') },
      ...this.cameras.map((camera) => ({ value: camera.id, label: `${camera.name} (${camera.id})` })),
    ]);
    cameraSelect.value = rule.condition.camera_id ?? '';
    refs.cameraId = cameraSelect;

    const severitySelect = el('select', { class: 'input input--sm' });
    fillSelect(severitySelect, [
      { value: '', label: t('triggers.any') },
      ...SEVERITIES.map((value) => ({ value, label: t(`severity.${value}`) })),
    ]);
    severitySelect.value = rule.condition.severity ?? '';
    refs.severity = severitySelect;

    const actionsContainer = el('div', { class: 'flag-list' },
      el('span', { class: 'flag-list__title' }, t('triggers.then', { count: rule.actions.length })),
    );
    for (const action of rule.actions) actionsContainer.append(this.renderAction(action, refs));
    const addActionBtn = el('button', {
      type: 'button', class: 'btn btn--sm',
      onClick: () => actionsContainer.insertBefore(
        this.renderAction({ type: this.actionTypes[0] ?? 'http_webhook', target: {} }, refs),
        addActionBtn,
      ),
    }, t('triggers.action.add'));
    actionsContainer.append(addActionBtn);

    const body = el('div', { class: 'task-card__body' },
      el('div', { class: 'field' }, el('label', {}, t('triggers.condition.task_type')), taskTypeSelect),
      el('div', { class: 'field' }, el('label', {}, t('triggers.condition.flag_id')), flagIdInput),
      el('div', { class: 'field' }, el('label', {}, t('triggers.condition.camera_id')), cameraSelect),
      el('div', { class: 'field' }, el('label', {}, t('triggers.condition.severity')), severitySelect),
      actionsContainer,
    );

    return el('article', { class: 'task-card', dataset: { id: rule.id } },
      el('header', { class: 'task-card__header' },
        el('span', { class: 'task-card__type' }, rule.id),
        el('span', { class: 'task-card__spacer' }),
        el('label', { class: 'switch' },
          enabledInput,
          el('span', { class: 'switch__track' }, el('span', { class: 'switch__thumb' })),
          el('span', {}, t('settings.flag_active')),
        ),
        el('button', {
          class: 'btn btn--danger btn--sm',
          onClick: () => this.removeRule(rule),
        }, t('settings.remove')),
      ),
      body,
      el('footer', { class: 'task-card__footer' },
        el('span', { class: 'task-card__note' }, t('triggers.save_note')),
        el('button', {
          class: 'btn btn--primary btn--sm',
          onClick: (event) => this.saveRule(rule, refs, event.currentTarget),
        }, t('settings.save')),
      ),
    );
  },

  /** One action row: a protocol select + a JSON textarea for its
   *  target, MVP-simple (no per-protocol field builder). */
  renderAction(action, refs) {
    const typeSelect = el('select', { class: 'input input--sm' });
    fillSelect(typeSelect, this.actionTypes.map((type) => ({ value: type, label: type })));
    typeSelect.value = action.type;

    const targetInput = el('textarea', {
      class: 'input', rows: '2', style: 'font-family: var(--font-mono); font-size: var(--fs-sm);',
    }, JSON.stringify(action.target ?? {}));

    const row = el('div', { style: 'display:flex; gap: var(--sp-2); align-items: flex-start;' },
      typeSelect,
      targetInput,
      el('button', {
        type: 'button', class: 'btn btn--sm btn--danger',
        onClick: () => {
          refs.actions = refs.actions.filter((entry) => entry !== rowRef);
          row.remove();
        },
      }, '×'),
    );

    const rowRef = { type: typeSelect, target: targetInput };
    refs.actions.push(rowRef);
    return row;
  },

  async saveRule(rule, refs, button) {
    const actions = [];
    for (const { type, target } of refs.actions) {
      let parsedTarget;
      try {
        parsedTarget = target.value.trim() ? JSON.parse(target.value) : {};
      } catch {
        toast(t('triggers.invalid_target_json', { type: type.value }), 'error');
        return;
      }
      actions.push({ type: type.value, target: parsedTarget });
    }

    const patch = {
      enabled: refs.enabled.checked,
      condition: {
        task_type: refs.taskType.value || null,
        flag_id: refs.flagId.value.trim() || null,
        camera_id: refs.cameraId.value || null,
        severity: refs.severity.value || null,
      },
      actions,
    };

    button.disabled = true;
    try {
      if (!await guard(api.updateTrigger(rule.id, patch))) return;
      await guard(api.reloadTriggers());
      toast(t('triggers.saved', { id: rule.id }), 'success');
      await this.load();
    } finally {
      button.disabled = false;
    }
  },

  async addRule() {
    const id = this.newIdInput.value.trim();
    if (!id) return;

    if (!await guard(api.addTrigger({ id, enabled: true, condition: {}, actions: [] }))) return;

    await guard(api.reloadTriggers());
    this.newIdInput.value = '';
    toast(t('triggers.added', { id }), 'success');
    await this.load();
  },

  async removeRule(rule) {
    if (!confirm(t('triggers.confirm_remove', { id: rule.id }))) return;

    if (!await guard(api.deleteTrigger(rule.id))) return;

    await guard(api.reloadTriggers());
    toast(t('triggers.removed'), 'success');
    await this.load();
  },

  // ------------------------------------------------------------------ //
  // Pending approvals
  // ------------------------------------------------------------------ //
  renderPending(pending) {
    const { flag, action } = pending;

    return el('article', { class: 'task-card' },
      el('header', { class: 'task-card__header' },
        el('span', { class: 'task-card__type' }, action.type),
        el('span', { class: 'task-card__spacer' }),
        el('span', { class: `badge badge--${flag.severity}` }, t(`severity.${flag.severity}`)),
      ),
      el('div', { class: 'task-card__body' },
        el('p', { style: 'grid-column: 1 / -1; margin: 0;' },
          `${flag.camera_id} · ${flag.task_type} · ${flag.flag_id}`),
        flag.message && el('p', { class: 'panel__hint', style: 'grid-column: 1 / -1; margin: 0;' }, flag.message),
      ),
      el('footer', { class: 'task-card__footer' },
        el('span', { class: 'task-card__spacer' }),
        el('button', {
          class: 'btn btn--danger btn--sm',
          onClick: () => this.resolvePending(pending.id, 'deny'),
        }, t('triggers.pending.deny')),
        el('button', {
          class: 'btn btn--primary btn--sm',
          onClick: () => this.resolvePending(pending.id, 'approve'),
        }, t('triggers.pending.approve')),
      ),
    );
  },

  async resolvePending(pendingId, action) {
    const call = action === 'approve' ? api.approvePendingTrigger(pendingId) : api.denyPendingTrigger(pendingId);
    if (!await guard(call)) return;

    toast(t(action === 'approve' ? 'triggers.pending.approved' : 'triggers.pending.denied'), 'success');
    await this.pollPending();
  },

  /** Rebuilds the cards after a language change. */
  retranslate() {
    this.load();
  },
};
