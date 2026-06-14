// District mode: everything maps 1:1 onto district-scoped endpoints, all
// aggregated with the same overlap-area weights — risk score, history,
// forecast, and the raw satellite observations behind them.
import {
  useDistrictForecast,
  useDistrictHistory,
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
import SectionTitle from './SectionTitle.jsx';

export default function DistrictDetails({ name }) {
  const history = useDistrictHistory(name);
  const forecast = useDistrictForecast(name);
  const satellite = useDistrictSatellite(name);
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

      <section aria-label="6-month forecast">
        <SectionTitle>6-month outlook ({unitNoun} average)</SectionTitle>
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
