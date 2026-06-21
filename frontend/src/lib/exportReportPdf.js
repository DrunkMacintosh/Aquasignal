// Export the rendered advisor report to PDF via the browser's native
// print-to-PDF. We deep-clone the report node into a hidden iframe that reuses
// the app's stylesheets (so Tailwind classes + fonts apply), strip anything
// marked data-export-exclude (the action buttons), and trigger print — the user
// chooses "Save as PDF". recharts SVGs print as crisp vectors, so there are no
// extra dependencies and no canvas-rasterization artifacts.

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c],
  );
}

/**
 * Print `node` (the report <article>) to PDF. No-op when there is no node or no
 * DOM (e.g. SSR / unit tests).
 *
 * @param {HTMLElement|null} node
 * @param {string} [title] - document title (becomes the default PDF filename)
 */
export function exportReportPdf(node, title = 'AquaSignal report') {
  if (!node || typeof document === 'undefined') return;

  // Clone so we can drop the action buttons without touching the live report.
  const clone = node.cloneNode(true);
  clone.querySelectorAll('[data-export-exclude]').forEach((el) => el.remove());

  // Reuse the app's own stylesheets (dev: <style>, prod: <link>) so the PDF
  // looks like the on-screen report.
  const styles = [...document.querySelectorAll('link[rel="stylesheet"], style')]
    .map((n) => n.outerHTML)
    .join('');

  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  Object.assign(iframe.style, {
    position: 'fixed',
    right: '0',
    bottom: '0',
    width: '0',
    height: '0',
    border: '0',
  });
  document.body.appendChild(iframe);

  const doc = iframe.contentWindow.document;
  doc.open();
  doc.write(
    '<!doctype html><html><head><meta charset="utf-8">' +
      styles +
      '<style>' +
      '@page{margin:14mm}' +
      // Print background colours (cards, badges, chart fills) instead of dropping them.
      '*{-webkit-print-color-adjust:exact;print-color-adjust:exact}' +
      'html,body{background:#fff;margin:0}' +
      '.pdf-wrap{max-width:760px;margin:0 auto;padding:4px}' +
      // Keep cards, charts and list rows from splitting across pages.
      'section,figure,li{break-inside:avoid}' +
      'h4{break-after:avoid}' +
      '</style>' +
      '<title>' +
      escapeHtml(title) +
      '</title></head><body><div class="pdf-wrap">' +
      clone.outerHTML +
      '</div>' +
      // Run inside the iframe: print once its stylesheets/fonts have loaded.
      '<script>window.onload=function(){setTimeout(function(){window.focus();window.print();},300);};<\/script>' +
      '</body></html>',
  );
  doc.close();

  const cleanup = () => {
    if (document.body.contains(iframe)) iframe.remove();
  };
  iframe.contentWindow.onafterprint = cleanup;
  // Fallback: some browsers don't fire onafterprint reliably.
  setTimeout(cleanup, 60000);
}
