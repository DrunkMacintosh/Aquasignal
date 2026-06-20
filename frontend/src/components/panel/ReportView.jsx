// Renders the advisor's report as an intricate, self-sufficient visual document:
// grounded charts (real snapshot data) interleaved with the AI's narrative and
// AI-derived charts (budget, drivers, targets, actions). The manifest
// (reportManifest.js) decides which charts appear, in what order, with what
// per-need copy — so each usage topic reads bespoke. Every section is skipped
// when it has no data, so a partial model response still renders cleanly.
import { useState } from 'react';
import { needLabel } from '../../lib/advisor.js';
import { manifestForNeed, normalizeAllocation } from '../../lib/reportManifest.js';
import TrajectoryChart from './charts/TrajectoryChart.jsx';
import WaterBalanceChart from './charts/WaterBalanceChart.jsx';
import RechargeGauge from './charts/RechargeGauge.jsx';
import AllocationDonut from './charts/AllocationDonut.jsx';
import RiskDriversBar from './charts/RiskDriversBar.jsx';
import KpiGauges from './charts/KpiGauges.jsx';
import PriorityActions from './charts/PriorityActions.jsx';

export default function ReportView({ report, need, district, snapshot = {} }) {
  const {
    headline,
    outlook,
    situation_assessment: situation,
    your_context: context,
    key_findings: findings = [],
    action_plan: plan = [],
    risks = [],
    monitoring = [],
    priority_actions: priorityActions = [],
  } = report;

  const manifest = manifestForNeed(need);
  const sections = manifest.sections.filter((s) => sectionHasData(s.key, report, snapshot));

  return (
    <article
      className="space-y-5 rounded-lg border border-ink/10 bg-paper/60 p-4"
      aria-label="Water-plan report"
    >
      <header>
        <div className="flex items-center justify-between gap-2">
          <p className="microlabel">
            {manifest.label} · {district}
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
        <p className="mt-1 text-xs text-ink-soft">{manifest.lede}</p>
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

      {/* Manifest-driven chart sections (order + copy vary per need). */}
      {sections.map((section) => (
        <ChartSection key={section.key} title={section.title} caption={section.caption} ai={section.source === 'ai'}>
          {renderChart(section.key, report, snapshot)}
        </ChartSection>
      ))}

      {/* Fallback: if the model gave no structured priority_actions but did give
          the legacy phased action_plan, show it so nothing is lost. */}
      {priorityActions.length === 0 && plan.length > 0 && (
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

      <CopyButton text={reportToText(report, manifest, district)} />
    </article>
  );
}

/** Whether a chart section has the data it needs (else ReportView skips it). */
function sectionHasData(key, report, snapshot) {
  switch (key) {
    case 'trajectory':
      return Boolean(snapshot.history?.length || snapshot.forecast?.length);
    case 'waterBalance':
      return (snapshot.satellite ?? []).some(
        (m) => m.precipitation != null || m.evapotranspiration != null,
      );
    case 'recharge':
      return snapshot.permeability_index != null || snapshot.recharge_value != null;
    case 'kpis':
      return (report.metrics ?? []).some((m) => m.label && m.value != null);
    case 'allocation':
      return normalizeAllocation(report.allocation).length > 0;
    case 'drivers':
      return (report.risk_drivers ?? []).some((d) => d.label && Number(d.weight) > 0);
    case 'priorityActions':
      return (report.priority_actions ?? []).some((a) => a.action);
    default:
      return false;
  }
}

function renderChart(key, report, snapshot) {
  switch (key) {
    case 'trajectory':
      return <TrajectoryChart history={snapshot.history} forecast={snapshot.forecast} />;
    case 'waterBalance':
      return <WaterBalanceChart satellite={snapshot.satellite} />;
    case 'recharge':
      return (
        <RechargeGauge
          permeabilityIndex={snapshot.permeability_index}
          permeabilityClass={snapshot.permeability_class}
          rechargeValue={snapshot.recharge_value}
          rechargeLabel={snapshot.recharge_label}
          netInfiltrationMm={snapshot.net_infiltration_mm}
        />
      );
    case 'kpis':
      return <KpiGauges metrics={report.metrics} />;
    case 'allocation':
      return <AllocationDonut allocation={report.allocation} />;
    case 'drivers':
      return <RiskDriversBar drivers={report.risk_drivers} />;
    case 'priorityActions':
      return <PriorityActions actions={report.priority_actions} />;
    default:
      return null;
  }
}

function Section({ title, children }) {
  return (
    <section aria-label={title}>
      <h5 className="microlabel mb-1.5">{title}</h5>
      {children}
    </section>
  );
}

// Chart section: title row with an optional "AI estimate" tag, optional caption.
function ChartSection({ title, caption, ai, children }) {
  return (
    <section aria-label={title}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <h5 className="microlabel">{title}</h5>
        {ai && (
          <span
            className="shrink-0 rounded-full border border-ink/10 bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-ink-faint"
            title="Planning estimate generated by the AI advisor — not a measurement."
          >
            AI estimate
          </span>
        )}
      </div>
      {caption && <p className="mb-2 text-[11px] text-ink-soft">{caption}</p>}
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

/** Flatten the report (text + structured blocks) to plain text for copy/paste. */
function reportToText(report, manifest, district) {
  const lines = [`AquaSignal — ${manifest.label} · ${district}`];
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

  if (report.metrics?.length) {
    lines.push('', 'KEY TARGETS');
    for (const m of report.metrics) {
      const target = m.target != null ? ` (target ${m.target}${m.unit ? ` ${m.unit}` : ''})` : '';
      lines.push(`- ${m.label}: ${m.value ?? '—'}${m.unit ? ` ${m.unit}` : ''}${target}`);
    }
  }
  const alloc = normalizeAllocation(report.allocation);
  if (alloc.length) {
    lines.push('', 'RECOMMENDED ALLOCATION');
    for (const a of alloc) lines.push(`- ${a.label}: ${Math.round(a.percent)}%`);
  }
  if (report.risk_drivers?.length) {
    lines.push('', 'RISK DRIVERS');
    for (const d of report.risk_drivers) lines.push(`- ${d.label}: ${Math.round(Number(d.weight))}/100`);
  }
  if (report.priority_actions?.length) {
    lines.push('', 'PRIORITY ACTIONS');
    for (const a of report.priority_actions) {
      const tf = a.timeframe ? `[${a.timeframe}] ` : '';
      lines.push(`- ${tf}${a.action} (impact ${a.impact}/5, effort ${a.effort}/5)`);
    }
  } else if (report.action_plan?.length) {
    lines.push('', 'ACTION PLAN');
    for (const phase of report.action_plan) {
      lines.push(phase.timeframe || '', ...(phase.actions || []).map((a) => `- ${a}`));
    }
  }

  listBlock('RISKS & WATCHPOINTS', report.risks);
  listBlock('MONITORING & NEXT STEPS', report.monitoring);
  return lines.join('\n');
}
