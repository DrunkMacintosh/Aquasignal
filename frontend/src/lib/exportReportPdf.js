// Export the rendered advisor report to PDF via the browser's native
// print-to-PDF. We deep-clone the report node into an off-screen iframe that
// reuses the app's stylesheets (so Tailwind classes + fonts apply), strip the
// action buttons (data-export-exclude), then trigger print from the PARENT once
// the iframe has loaded — the user chooses "Save as PDF". recharts SVGs print as
// crisp vectors, so there are no extra dependencies.
//
// Robustness notes (these are the things that silently break print-to-iframe):
//  - The iframe must have REAL dimensions; a 0x0 iframe prints a blank page in
//    Chromium. We give it A4 px size and hide it off-screen instead.
//  - We load content via `srcdoc` and trigger print from the parent's onload,
//    rather than document.write + an injected inline <script>. The latter races
//    the load event (handler can attach after load already fired) and is blocked
//    under a strict CSP. srcdoc fires onload reliably and needs no inline script.

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

  // Reuse the app's own stylesheets (dev: <style>, prod: <link>) plus any font
  // links from <head>, so the PDF looks like the on-screen report.
  const styles = [
    ...document.querySelectorAll('link[rel="stylesheet"], style, link[as="font"], link[rel="preconnect"]'),
  ]
    .map((n) => n.outerHTML)
    .join('');

  const html =
    '<!doctype html><html><head><meta charset="utf-8">' +
    styles +
    '<style>' +
    '@page{margin:14mm}' +
    // Print background colours (cards, badges, chart fills) instead of dropping them.
    '*{-webkit-print-color-adjust:exact;print-color-adjust:exact}' +
    'html,body{background:#fff;margin:0}' +
    '.pdf-wrap{max-width:760px;margin:0 auto;padding:4px}' +
    // Keep cards, charts and list rows from splitting across pages.
    'section,figure,li{break-inside:avoid}h4{break-after:avoid}' +
    '</style><title>' +
    escapeHtml(title) +
    '</title></head><body><div class="pdf-wrap">' +
    clone.outerHTML +
    '</div></body></html>';

  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  // Real A4-ish size (so the document lays out) but parked off-screen.
  Object.assign(iframe.style, {
    position: 'fixed',
    left: '-9999px',
    top: '0',
    width: '794px',
    height: '1123px',
    border: '0',
    opacity: '0',
    pointerEvents: 'none',
  });

  let printed = false;
  const cleanup = () => {
    if (document.body.contains(iframe)) iframe.remove();
  };

  iframe.onload = () => {
    const cdoc = iframe.contentDocument;
    // Ignore the initial about:blank load; only print once our content is in.
    if (printed || !cdoc || !cdoc.querySelector('.pdf-wrap')) return;
    printed = true;
    // Let fonts/stylesheets settle, then print from the parent.
    setTimeout(() => {
      const win = iframe.contentWindow;
      try {
        win.onafterprint = cleanup;
        win.focus();
        win.print();
      } catch {
        cleanup();
        return;
      }
      // Fallback cleanup if onafterprint never fires.
      setTimeout(cleanup, 60000);
    }, 400);
  };

  // Set srcdoc before insertion so the iframe loads our content directly.
  iframe.srcdoc = html;
  document.body.appendChild(iframe);
}
