/* =====================================================================
   MittiMandi Shared Component: Badges & Provenance Tags
   Authoritative: Rural Commerce Material Baseline (6dp radius, strict tokens)
   Provenance Types: Actual, Forecast, Estimate, Recommendation
   Additional Variants: Grade, Source, Fallback, Sync
   ===================================================================== */

export function renderBadge(text, variant = 'primary', extraClasses = '') {
  return `<span class="badge badge-${variant} ${extraClasses}">${text}</span>`;
}

export function renderProvenanceBadge(type = 'actual', text = '') {
  const t = String(type).toLowerCase();
  if (t === 'forecast') {
    return `<span class="badge badge-forecast">📈 ${text || 'Forecast'}</span>`;
  } else if (t === 'estimate') {
    return `<span class="badge badge-estimate">≈ ${text || 'Estimate'}</span>`;
  } else if (t === 'recommendation') {
    return `<span class="badge badge-recommendation">${text || 'Recommendation'}</span>`;
  }
  return `<span class="badge badge-actual">✓ ${text || 'Actual'}</span>`;
}

export function renderActualBadge(text = 'Actual') {
  return renderProvenanceBadge('actual', text);
}

export function renderForecastBadge(text = 'Forecast') {
  return renderProvenanceBadge('forecast', text);
}

export function renderEstimateBadge(text = 'Estimate') {
  return renderProvenanceBadge('estimate', text);
}

export function renderRecommendationBadge(text = 'Recommendation') {
  return renderProvenanceBadge('recommendation', text);
}

export function renderGradeBadge(grade = 'Grade A') {
  const g = String(grade || '').toUpperCase();
  let variant = 'grade-a';
  if (g.includes('B')) variant = 'grade-b';
  else if (g.includes('C')) variant = 'grade-c';
  return `<span class="badge badge-${variant}">${grade}</span>`;
}

export function renderSourceBadge(source = 'internal') {
  const isNet = source === 'network' || source === true;
  const label = isNet ? '🌐 ONDC Network' : '🏢 Internal Estimate';
  const variant = isNet ? 'source-net' : 'source-int';
  return `<span class="badge badge-${variant}">${label}</span>`;
}

export function renderFallbackBadge(fallback = null) {
  if (!fallback || fallback === 'ai' || fallback === 'onnx') {
    return `<span class="badge badge-fallback-onnx">✓ AI Vision Graded</span>`;
  }
  return `<span class="badge badge-fallback-rule">⚠ Rule-based Fallback</span>`;
}

export function renderSyncBadge(status = 'synced') {
  const s = String(status || '').toLowerCase();
  if (s === 'synced') {
    return `<span class="badge badge-sync-synced">✓ Synced</span>`;
  } else if (s === 'outbox' || s === 'pending' || s === 'created' || s === 'updated') {
    return `<span class="badge badge-sync-outbox">⏳ Outbox (${s})</span>`;
  } else if (s === 'conflict') {
    return `<span class="badge badge-sync-conflict">⚠️ Conflict</span>`;
  }
  return `<span class="badge badge-sync-offline">✈️ Offline</span>`;
}
