/* =====================================================================
   MittiMandi Shared Component: Form Inputs & Controls
   CSP-Safe: uses data-change instead of inline onchange
   ===================================================================== */

export function renderFormGroup({
  label = '',
  helper = '',
  controlHtml = '',
  error = '',
  id = ''
} = {}) {
  return `
    <div class="form-group ${error ? 'has-error' : ''}">
      ${label ? `
        <label class="form-label" ${id ? `for="${id}"` : ''}>
          <span>${label}</span>
          ${helper ? `<span class="helper">${helper}</span>` : ''}
        </label>
      ` : ''}
      ${controlHtml}
      ${error ? `<span class="form-error-msg">⚠️ ${error}</span>` : ''}
    </div>
  `;
}

export function renderPhoneInput({
  id = 'login-phone',
  value = '',
  label = 'Phone Number',
  helper = 'WhatsApp / SMS OTP',
  error = ''
} = {}) {
  const control = `
    <div class="phone-input-row">
      <div class="phone-prefix" aria-hidden="true">
        <span class="phone-flag">🇮🇳</span>
        <span>+91</span>
      </div>
      <input type="tel" id="${id}" class="input-box phone-input" value="${value}" placeholder="98765 43210" maxlength="10" autocomplete="tel">
    </div>
  `;
  return renderFormGroup({ label, helper, controlHtml: control, error, id });
}

export function renderTextInput({
  id = '',
  type = 'text',
  value = '',
  placeholder = '',
  label = '',
  helper = '',
  error = '',
  step = '',
  min = '',
  max = ''
} = {}) {
  const stepAttr = step ? `step="${step}"` : '';
  const minAttr = min !== '' ? `min="${min}"` : '';
  const maxAttr = max !== '' ? `max="${max}"` : '';
  const control = `<input type="${type}" id="${id}" class="input-box" value="${value}" placeholder="${placeholder}" ${stepAttr} ${minAttr} ${maxAttr}>`;
  return renderFormGroup({ label, helper, controlHtml: control, error, id });
}

export function renderSelect({
  id = '',
  options = [], // [{ value: 'Wheat', label: 'Wheat (Sharbati)' }]
  selected = '',
  label = '',
  helper = '',
  error = ''
} = {}) {
  const optsHtml = options.map(opt => {
    const val = typeof opt === 'string' ? opt : opt.value;
    const txt = typeof opt === 'string' ? opt : opt.label;
    const isSel = val === selected ? 'selected' : '';
    return `<option value="${val}" ${isSel}>${txt}</option>`;
  }).join('');

  const control = `<select id="${id}" class="input-box select-box">${optsHtml}</select>`;
  return renderFormGroup({ label, helper, controlHtml: control, error, id });
}

export function renderCheckbox({
  id = '',
  checked = false,
  labelHtml = '',
  action = '',
  changeAction = ''
} = {}) {
  const chkAttr = checked ? 'checked' : '';
  const resolved = action || changeAction;
  const changeAttr = resolved ? `data-change="${resolved}"` : '';
  return `
    <div class="checkbox-row">
      <input type="checkbox" id="${id}" class="checkbox-input" ${chkAttr} ${changeAttr}>
      <label for="${id}" class="checkbox-label">${labelHtml}</label>
    </div>
  `;
}
