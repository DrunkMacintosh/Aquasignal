// Authenticated file downloads: exports require the Authorization header, so
// a plain <a href> cannot be used. The blob is fetched via axios and handed
// to the browser through a short-lived object URL instead.

export function filenameFromDisposition(header, fallback) {
  const match = /filename="?([^";]+)"?/i.exec(header ?? '');
  return match ? match[1] : fallback;
}

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
