// Deep-analysis water planner for one district: pick a goal -> fill a structured
// site-profile form -> get a report grounded in BOTH the district snapshot and
// figures calculated from the user's own inputs. No open chat. State is
// component-local and resets when the panel switches district (parent keys this
// by district name).
import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { fetchAdvisorReport } from '../../api/client.js';
import {
  useDistrictForecast,
  useDistrictHistory,
  useDistrictPermeability,
  useDistrictSatellite,
} from '../../api/hooks.js';
import { ADVISOR_NEEDS, buildSnapshot } from '../../lib/advisor.js';
import { computeSiteMetrics } from '../../lib/siteProfile.js';
import ReportView from './ReportView.jsx';
import SiteProfileForm from './SiteProfileForm.jsx';

export default function AdvisorPlanner({ district }) {
  // Build the data snapshot from the (already-cached) district queries, so the
  // popout only needs the district name.
  const history = useDistrictHistory(district);
  const forecast = useDistrictForecast(district);
  const satellite = useDistrictSatellite(district);
  const permeability = useDistrictPermeability(district);
  const snapshot = useMemo(
    () =>
      buildSnapshot({
        monthly: history.data?.monthly,
        forecast: forecast.data?.forecast,
        satellite: satellite.data?.observations,
        permeability: permeability.data,
      }),
    [history.data, forecast.data, satellite.data, permeability.data],
  );

  const [need, setNeed] = useState(null);
  const [site, setSite] = useState(null); // computed site metrics (grounded)
  const [report, setReport] = useState(null);

  const reportM = useMutation({
    mutationFn: ({ siteSummary }) =>
      fetchAdvisorReport({ districtName: district, need, snapshot, siteSummary }),
    onSuccess: (data) => setReport(data.report),
  });

  function handleSubmit(inputs) {
    const computed = computeSiteMetrics(need, inputs, snapshot);
    setSite(computed);
    reportM.mutate({ siteSummary: computed?.summaryForAi ?? '' });
  }

  function reset() {
    setNeed(null);
    setSite(null);
    setReport(null);
    reportM.reset();
  }

  // Step: goal picker
  if (!need) return <NeedPicker district={district} onPick={setNeed} />;

  // Step: finished report
  if (report) {
    return (
      <div className="space-y-2">
        <ReportView report={report} need={need} district={district} snapshot={snapshot} site={site} />
        <button
          type="button"
          onClick={reset}
          className="text-xs font-semibold text-ink-soft underline-offset-2 hover:text-ink hover:underline"
        >
          ← Start a new plan
        </button>
      </div>
    );
  }

  // Step: site-profile form (loading report on submit)
  return (
    <SiteProfileForm
      need={need}
      district={district}
      isSubmitting={reportM.isPending}
      error={reportM.isError ? reportM.error : null}
      onSubmit={handleSubmit}
      onCancel={reset}
    />
  );
}

function NeedPicker({ district, onPick }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
      <p className="text-sm font-semibold">Plan your water use with AI</p>
      <p className="mt-1 text-xs text-ink-soft">
        Pick a goal. The advisor reviews {district}'s risk, forecast, and recharge data, asks a
        few short questions about your site, then writes a deep-analysis report.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ADVISOR_NEEDS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => onPick(option.id)}
            className="rounded-lg border border-ink/15 bg-surface px-3 py-2.5 text-left transition-colors hover:border-water hover:bg-water/5 focus-visible:outline-water"
          >
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="mt-0.5 block text-xs text-ink-soft">{option.blurb}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
