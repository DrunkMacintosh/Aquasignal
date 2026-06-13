// Authenticated CSV/PDF downloads (the export endpoints require the bearer
// token, so the files are fetched as blobs rather than via plain links).
import { useState } from 'react';
import { downloadCsvFile, downloadPdfFile } from '../api/client.js';
import { saveBlob } from '../lib/download.js';

export default function ExportButtons({ district }) {
  const [busy, setBusy] = useState(null); // 'csv' | 'pdf' | null
  const [error, setError] = useState(null);

  async function handleDownload(kind, fetcher) {
    setBusy(kind);
    setError(null);
    try {
      const { blob, filename } = await fetcher(district);
      saveBlob(blob, filename);
    } catch {
      setError('Download failed — please try again.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="flex gap-2.5">
        <button
          type="button"
          className="btn-secondary flex-1"
          disabled={busy !== null}
          onClick={() => handleDownload('csv', downloadCsvFile)}
          aria-label={`Download ${district} risk data as CSV`}
        >
          {busy === 'csv' ? 'Preparing…' : '⤓ Download CSV'}
        </button>
        <button
          type="button"
          className="btn-primary flex-1"
          disabled={busy !== null}
          onClick={() => handleDownload('pdf', downloadPdfFile)}
          aria-label={`Download ${district} PDF report`}
        >
          {busy === 'pdf' ? 'Preparing…' : '⤓ PDF Report'}
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-xs font-medium text-risk-critical">
          {error}
        </p>
      )}
    </div>
  );
}
