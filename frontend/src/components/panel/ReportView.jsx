// Renders the advisor's structured report as a sectioned document. Every field
// is optional (the backend defaults them), so each section only renders when it
// has content.
import { useState } from 'react';
import { needLabel } from '../../lib/advisor.js';

export default function ReportView({ report, need, district }) {
  const {
    headline,
    outlook,
    situation_assessment: situation,
    your_context: context,
    key_findings: findings = [],
    action_plan: plan = [],
    risks = [],
    monitoring = [],
  } = report;

  return (
    <article
      className="space-y-4 rounded-lg border border-ink/10 bg-paper/60 p-4"
      aria-label="Water-plan report"
    >
      <header>
        <div className="flex items-center justify-between gap-2">
          <p className="microlabel">
            {needLabel(need)} · {district}
          </p>
          {outlook && (
            <span className="shrink-0 rounded-full border border-water/40 bg-water/10 px-2 py-0.5 text-xs font-semibold text-water">
              {outlook}
            </span>
          )}
        </div>
        {headline && (
          <h4 className="mt-1 font-display text-lg font-semibold leading-snug">{headline}</h4>
        )}
      </header>

      {situation && (
        <Section title="Situation assessment">
          <p className="text-sm leading-relaxed text-ink">{situation}</p>
        </Section>
      )}
      {context && (
        <Section title="Your context">
          <p className="text-sm leading-relaxed text-ink-soft">{context}</p>
        </Section>
      )}
      {findings.length > 0 && (
        <Section title="Key findings">
          <Bullets items={findings} />
        </Section>
      )}
      {plan.length > 0 && (
        <Section title="Action plan">
          <div className="space-y-3">
            {plan.map((phase, i) => (
              <div key={i}>
                {phase.timeframe && (
                  <p className="text-xs font-semibold uppercase tracking-wide text-water">
                    {phase.timeframe}
                  </p>
                )}
                <Bullets items={phase.actions} />
              </div>
            ))}
          </div>
        </Section>
      )}
      {risks.length > 0 && (
        <Section title="Risks & watchpoints">
          <Bullets items={risks} />
        </Section>
      )}
      {monitoring.length > 0 && (
        <Section title="Monitoring & next steps">
          <Bullets items={monitoring} />
        </Section>
      )}

      <CopyButton text={reportToText(report, need, district)} />
    </article>
  );
}

function Section({ title, children }) {
  return (
    <section aria-label={title}>
      <h5 className="microlabel mb-1.5">{title}</h5>
      {children}
    </section>
  );
}

function Bullets({ items = [] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-lg border border-ink/15 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:bg-surface hover:text-ink"
    >
      {copied ? 'Copied ✓' : 'Copy report'}
    </button>
  );
}

/** Flatten the report to plain text for copy/paste. */
function reportToText(report, need, district) {
  const lines = [`AquaSignal water plan — ${needLabel(need)} · ${district}`];
  if (report.outlook) lines.push(`Outlook: ${report.outlook}`);
  if (report.headline) lines.push(report.headline);
  const block = (title, body) => {
    if (body) lines.push('', title, body);
  };
  const listBlock = (title, items = []) => {
    if (items.length) lines.push('', title, ...items.map((i) => `- ${i}`));
  };
  block('SITUATION ASSESSMENT', report.situation_assessment);
  block('YOUR CONTEXT', report.your_context);
  listBlock('KEY FINDINGS', report.key_findings);
  if (report.action_plan?.length) {
    lines.push('', 'ACTION PLAN');
    for (const phase of report.action_plan) {
      lines.push(phase.timeframe || '', ...(phase.actions || []).map((a) => `- ${a}`));
    }
  }
  listBlock('RISKS & WATCHPOINTS', report.risks);
  listBlock('MONITORING & NEXT STEPS', report.monitoring);
  return lines.join('\n');
}
