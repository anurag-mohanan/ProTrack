/** Helpers for keyboard / focus-safe form editing. */

/**
 * True when the event target is an editable field where global shortcuts
 * must not intercept typing (INPUT, TEXTAREA, SELECT, contenteditable).
 */
export function isEditableKeyboardTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  if (target.closest('[contenteditable="true"]')) return true;
  // MUI Select / Autocomplete / DatePicker often focus inner divs with role
  if (target.closest('[role="textbox"], [role="combobox"], [role="searchbox"]')) {
    return true;
  }
  return false;
}
