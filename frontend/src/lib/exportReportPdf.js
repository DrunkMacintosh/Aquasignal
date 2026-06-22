// Export the rendered advisor report as a downloadable PDF FILE (no print
// dialog). We rasterize the report node with html2canvas, write the image into
// a multi-page A4 PDF with jsPDF, and trigger a download. Both libraries are
// dynamically imported so they are code-split out of the main bundle and only
// fetched the first time someone exports.
//
// recharts charts are SVG; html2canvas rasterizes them into the page image. The
// action buttons are skipped via `ignoreElements` so they don't appear in the
// PDF.

function pdfFilename(title) {
  const base =
    String(title)
      .replace(/[^\w.-]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'AquaSignal-report';
  return `${base}.pdf`;
}

/**
 * Generate and download a PDF of the report `node`. Resolves once the download
 * has been triggered. No-op without a node or DOM (SSR / unit tests).
 *
 * @param {HTMLElement|null} node
 * @param {string} [title] - used for the downloaded filename
 * @returns {Promise<void>}
 */
export async function exportReportPdf(node, title = 'AquaSignal report') {
  if (!node || typeof document === 'undefined') return;

  const [{ default: html2canvas }, jspdf] = await Promise.all([
    import('html2canvas'),
    import('jspdf'),
  ]);
  const JsPDF = jspdf.jsPDF || jspdf.default;

  const canvas = await html2canvas(node, {
    scale: 2, // render at 2x for a crisp result
    backgroundColor: '#ffffff',
    useCORS: true,
    logging: false,
    // Don't paint the action row (Copy / Export buttons) into the PDF.
    ignoreElements: (el) =>
      el.nodeType === 1 && typeof el.hasAttribute === 'function' && el.hasAttribute('data-export-exclude'),
  });

  const pdf = new JsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  const imgW = pageW;
  const imgH = (canvas.height / canvas.width) * imgW;
  // JPEG (on the white background) keeps the file small — a PNG of a scale-2
  // capture runs to ~10 MB; JPEG at high quality is ~1-2 MB and still crisp.
  const imgData = canvas.toDataURL('image/jpeg', 0.92);

  // Single page, or slice the tall image across pages by shifting it up.
  let position = 0;
  let heightLeft = imgH;
  pdf.addImage(imgData, 'JPEG', 0, position, imgW, imgH);
  heightLeft -= pageH;
  while (heightLeft > 0) {
    position -= pageH;
    pdf.addPage();
    pdf.addImage(imgData, 'JPEG', 0, position, imgW, imgH);
    heightLeft -= pageH;
  }

  pdf.save(pdfFilename(title));
}
