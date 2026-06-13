// District-scoped services inside the cell view: the backend keys reports and
// alerts on district names, so the user picks the district once (remembered
// for next time). Cell-level history/satellite data live directly in
// CellDetails — this section is only the district-keyed extras.
import { useState } from 'react';
import { useDistrictRiskMap } from '../../api/hooks.js';
import { districtNamesFrom } from '../../lib/districts.js';
import AlertSubscribe from '../AlertSubscribe.jsx';
import ExportButtons from '../ExportButtons.jsx';
import SectionTitle from './SectionTitle.jsx';

const LAST_DISTRICT_KEY = 'aquasignal.last-district';

export default function DistrictServices() {
  const [district, setDistrict] = useState(
    () => localStorage.getItem(LAST_DISTRICT_KEY) ?? '',
  );
  const districtMap = useDistrictRiskMap(); // cached — shares the map view's query
  const districtNames = districtNamesFrom(districtMap.data);

  function handleChange(event) {
    const value = event.target.value;
    setDistrict(value);
    localStorage.setItem(LAST_DISTRICT_KEY, value);
  }

  return (
    <div className="space-y-6 border-t border-ink/10 pt-5">
      <section aria-label="District selection">
        <SectionTitle>District · reports &amp; alerts</SectionTitle>
        <select
          value={district}
          onChange={handleChange}
          aria-label="Select the district this cell belongs to"
          className="w-full rounded-lg border border-ink/15 bg-surface px-3 py-2.5 text-sm font-medium focus-visible:outline-water"
        >
          <option value="">Select a district…</option>
          {districtNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </section>

      {district && (
        <>
          <section aria-label="Reports">
            <SectionTitle>Reports for your supervisor</SectionTitle>
            <ExportButtons district={district} />
          </section>

          <section aria-label="Alerts">
            <SectionTitle>Alerts</SectionTitle>
            <AlertSubscribe district={district} />
          </section>
        </>
      )}
    </div>
  );
}
