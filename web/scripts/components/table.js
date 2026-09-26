/* =====================================================================
   MittiMandi Shared Component: Accessible Data Table
   ===================================================================== */

export function renderTable({
  headers = [], // ['Commodity', 'Grade', 'Price']
  rows = [],    // [['Wheat', 'Grade A', '₹2,850']]
  caption = '',
  extraClasses = ''
} = {}) {
  const headHtml = headers.map(h => {
    const label = typeof h === 'string' ? h : h.label;
    const alignClass = typeof h === 'object' && h.align ? `class="text-${h.align}"` : '';
    return `<th ${alignClass}>${label}</th>`;
  }).join('');

  const bodyHtml = rows.map(row => {
    const cells = row.map((cell, idx) => {
      const h = headers[idx];
      const alignClass = typeof h === 'object' && h.align ? `class="text-${h.align}"` : '';
      return `<td ${alignClass}>${cell}</td>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  return `
    <div class="table-container ${extraClasses}">
      <table class="data-table">
        ${caption ? `<caption class="sr-only">${caption}</caption>` : ''}
        <thead><tr>${headHtml}</tr></thead>
        <tbody>${bodyHtml || '<tr><td colspan="' + headers.length + '" class="text-center text-muted">No records</td></tr>'}</tbody>
      </table>
    </div>
  `;
}
