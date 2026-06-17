// District mode: everything maps 1:1 onto district-scoped endpoints, all
// aggregated with the same overlap-area weights — risk score, history,
// forecast, and the raw satellite observations behind them.
import {
  useAdvisorConfig,
  useDistrictForecast,
  useDistrictHistory,
  useDistrictPermeability,
  useDistrictSatellite,
} from '../../api/hooks.js';
import { trendFromHistory } from '../../lib/risk.js';
import { adminUnitNoun } from '../../lib/adminUnits.js';
import AlertSubscribe from '../AlertSubscribe.jsx';
import ExportButtons from '../ExportButtons.jsx';
import ForecastChart from '../ForecastChart.jsx';
import RiskScoreCard from '../RiskScoreCard.jsx';
import SatelliteObservations from '../SatelliteObservations.jsx';
import Sparkline from '../Sparkline.jsx';
import { PanelSkeleton } from '../Skeletons.jsx';
import PermeabilityCard from './PermeabilityCard.jsx';
import SectionTitle from './SectionTitle.jsx';

export default function DistrictDetails({ name, onPlanWithAi, onSeeHistory }) {
  const history = useDistrictHistory(name);
  const forecast = useDistrictForecast(name);
  const satellite = useDistrictSatellite(name);
  const permeability = useDistrictPermeability(name);
  const advisorConfig = useAdvisorConfig();
  const unitNoun = adminUnitNoun(name);

  if (history.isPending) return <PanelSkeleton />;
  if (history.isError) {
    return (
      <p className="p-5 text-sm text-ink-soft">
        Could not load data for {name}. Check the {unitNoun} name and try again.
      </p>
    );
  }

  const monthly = history.data.monthly;
  const latest = monthly[monthly.length - 1];

  return (
    <div className="space-y-6 p-5">
      {latest ? (
        <RiskScoreCard
          risk={latest.risk}
          trend={trendFromHistory(monthly)}
          month={latest.month}
        />
      ) : (
        <p className="text-sm text-ink-soft">
          No risk scores for this {unitNoun} yet — its grid cells fall outside the satellite
          coverage (open water or sensor gaps). Raw observations may still appear below.
        </p>
      )}

      {advisorConfig.data?.enabled && onPlanWithAi && (
        <button
          type="button"
          onClick={onPlanWithAi}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-water/40 bg-water/10 px-4 py-2.5 text-sm font-semibold text-water transition-colors hover:bg-water/15 focus-visible:outline-water"
        >
          <span aria-hidden="true">✦</span> Plan your water use with AI
        </button>
      )}

      <section aria-label="6-month forecast">
        <div className="mb-2.5 flex items-baseline justify-between gap-3">
          <h3 className="microlabel">6-month outlook ({unitNoun} average)</h3>
          {onSeeHistory && monthly.length > 0 && (
            <button
              type="button"
              onClick={onSeeHistory}
              className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-ink/10 px-2.5 py-1 text-xs font-semibold text-ink-soft transition-colors hover:bg-paper hover:text-ink focus-visible:outline-water"
            >
              See history
              <span aria-hidden="true">→</span>
            </button>
          )}
        </div>
        {forecast.isError ? (
          <p className="text-sm text-ink-soft">Forecast could not be loaded.</p>
        ) : (
          <ForecastChart points={forecast.data?.forecast} isLoading={forecast.isPending} />
        )}
      </section>

      {monthly.length > 0 && (
        <section aria-label="Risk history">
          <SectionTitle>Last {monthly.length} months</SectionTitle>
          <Sparkline points={monthly} />
        </section>
      )}

      <section aria-label="Satellite observations">
        <SectionTitle>Satellite observations</SectionTitle>
        <SatelliteObservations
          observations={satellite.data?.observations}
          isLoading={satellite.isPending}
          isError={satellite.isError}
        />
      </section>

      <section aria-label="Permeability and recharge">
        <SectionTitle>Permeability &amp; recharge</SectionTitle>
        <PermeabilityCard
          data={permeability.data}
          isLoading={permeability.isPending}
          isError={permeability.isError}
        />
      </section>

      <section aria-label="Reports">
        <SectionTitle>Reports for your supervisor</SectionTitle>
        <ExportButtons district={name} />
      </section>

      <section aria-label="Alerts">
        <SectionTitle>Alerts</SectionTitle>
        <AlertSubscribe district={name} />
      </section>
    </div>
  );
}
