// Structured per-need site-profile form. Replaces the old AI free-text intake:
// typed fields (number/select) with units, so the answers can drive a real
// compute engine (lib/siteProfile.js) rather than only flavouring the prompt.
// Owns its field values; hands the filled inputs back on submit.
import { useState } from 'react';
import { hasRequiredSiteInputs, siteFieldsFor } from '../../lib/siteProfile.js';
import { needLabel } from '../../lib/advisor.js';
import { Button, Card } from '../ui';

export default function SiteProfileForm({ need, district, isSubmitting, error, onSubmit, onCancel }) {
  const fields = siteFieldsFor(need);
  const [values, setValues] = useState({});
  const [notes, setNotes] = useState(''); // free-text "anything else" for this topic
  const ready = hasRequiredSiteInputs(need, values);

  function setField(id, value) {
    setValues((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <Card className="!rounded-lg !bg-paper/60 shadow-none">
      <p className="text-sm font-semibold">
        {needLabel(need)} · {district}
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        Tell us about your site. We use it to calculate your own water figures and tailor the
        plan — leave optional fields blank if unsure.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && !isSubmitting) onSubmit(values, notes);
        }}
        className="mt-3 space-y-3"
      >
        {fields.map((field) => (
          <SiteField key={field.id} field={field} value={values[field.id] ?? ''} onChange={setField} disabled={isSubmitting} />
        ))}

        <div>
          <label htmlFor="site-notes" className="block text-sm font-medium">
            Other information you want to add
            <span className="ml-1 text-xs font-normal text-ink-faint">(optional)</span>
          </label>
          <textarea
            id="site-notes"
            value={notes}
            maxLength={1000}
            rows={3}
            placeholder="Anything important the questions above didn't cover — e.g. budget limits, recent well changes, local constraints."
            disabled={isSubmitting}
            onChange={(event) => setNotes(event.target.value)}
            className="mt-1 w-full resize-y rounded-lg border border-ink/15 bg-surface px-3 py-2 text-sm focus-visible:outline-water disabled:opacity-50"
          />
        </div>

        {error && (
          <p role="alert" className="text-xs font-medium text-risk-critical">
            {error.response?.status === 429
              ? 'The advisor is busy right now (high demand). Wait a moment and try again.'
              : 'The advisor is unavailable right now. Please try again.'}
          </p>
        )}

        <div className="flex items-center gap-3">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={!ready || isSubmitting}
            className="!py-2 text-sm"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-1.5">
                Analyzing <LoadingDots />
              </span>
            ) : (
              'Generate report'
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        {!ready && (
          <p className="text-xs text-ink-soft">Fill the starred field to continue.</p>
        )}
      </form>
    </Card>
  );
}

function SiteField({ field, value, onChange, disabled }) {
  const id = `site-${field.id}`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {field.label}
        {field.required && <span className="ml-0.5 text-water" aria-hidden="true">*</span>}
        {field.unit && <span className="ml-1 text-xs font-normal text-ink-faint">({field.unit})</span>}
      </label>
      {field.type === 'select' ? (
        <select
          id={id}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(field.id, event.target.value)}
          className="mt-1 w-full rounded-lg border border-ink/15 bg-surface px-3 py-2 text-sm focus-visible:outline-water disabled:opacity-50"
        >
          <option value="">{field.placeholder || 'Select…'}</option>
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          value={value}
          placeholder={field.placeholder || ''}
          disabled={disabled}
          onChange={(event) => onChange(field.id, event.target.value)}
          className="mt-1 w-full rounded-lg border border-ink/15 bg-surface px-3 py-2 text-sm focus-visible:outline-water disabled:opacity-50"
        />
      )}
    </div>
  );
}

// Reused "AI is working" indicator (mirrors AdvisorPlanner's dots).
function LoadingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden="true">
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-dot-bounce" />
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-dot-bounce [animation-delay:0.15s]" />
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-dot-bounce [animation-delay:0.3s]" />
    </span>
  );
}
