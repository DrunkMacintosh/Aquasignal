// Cell mode: score/trend come straight from the clicked GeoJSON feature; the
// forecast, history, and raw satellite observations come from the cell
// endpoints. Reports and alerts are district-scoped on the backend, so they
// live behind a district picker.
import { useCellForecast, useCellHistory, useCellSatellite } from '../../api/hooks.js';
import ForecastChart from '../ForecastChart.jsx';
import { RiskScoreCard } from '../ui';
import SatelliteObservations from '../SatelliteObservations.jsx';
import Sparkline from '../Sparkline.jsx';
import DistrictServices from './DistrictServices.jsx';
import SectionTitle from './SectionTitle.jsx';

export default function CellDetails({ cell, month }) {
  const forecast = useCellForecast(cell.cell_id);
  const history = useCellHistory(cell.cell_id);
  const satellite = useCellSatellite(cell.cell_id);

  return (
    <div className="stagger space-y-6 p-5">
      <RiskScoreCard risk={cell.current_risk} trend={cell.trend} month={month} />

      <section aria-label="6-month forecast">
        <SectionTitle>6-month outlook</SectionTitle>
        {forecast.isError ? (
          <p className="text-sm text-ink-soft">Forecast could not be loaded.</p>
        ) : (
          <ForecastChart points={forecast.data?.forecast} isLoading={forecast.isPending} animate />
        )}
      </section>

      <section aria-label="Risk history">
        <SectionTitle>Risk history</SectionTitle>
        {history.isError ? (
          <p className="text-sm text-ink-soft">History could not be loaded.</p>
        ) : (
          <Sparkline points={history.data?.history} isLoading={history.isPending} animate />
        )}
      </section>

      <section aria-label="Satellite observations">
        <SectionTitle>Satellite observations</SectionTitle>
        <SatelliteObservations
          observations={satellite.data?.observations}
          isLoading={satellite.isPending}
          isError={satellite.isError}
        />
      </section>

      <DistrictServices />
    </div>
  );
}
