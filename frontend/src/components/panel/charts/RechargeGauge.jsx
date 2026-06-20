// Grounded: a radial gauge of soil permeability (0-1 -> 0-100%) — how freely
// water can infiltrate — paired with the district's relative recharge potential
// readout. A "circle graph" for the aquifer's ability to replenish itself.
import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from 'recharts';
import { CHART } from '../../../lib/reportManifest.js';

// Permeability bands -> colour, mirroring the verbal classes from the pipeline.
function permeabilityColor(index) {
  if (index >= 0.66) return CHART.risk.low; // free-draining
  if (index >= 0.33) return '#E0A93B'; // moderate
  return CHART.risk.high; // tight / impermeable
}

export default function RechargeGauge({
  permeabilityIndex = null,
  permeabilityClass = null,
  rechargeValue = null,
  rechargeLabel = null,
  netInfiltrationMm = null,
}) {
  const hasIndex = permeabilityIndex != null;
  if (!hasIndex && rechargeValue == null) return null;

  const pct = hasIndex ? Math.round(permeabilityIndex * 100) : 0;
  const color = permeabilityColor(permeabilityIndex ?? 0);
  const data = [{ name: 'permeability', value: pct, fill: color }];

  return (
    <figure
      className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-5"
      aria-label={`Soil permeability ${pct} percent, recharge potential ${rechargeLabel ?? 'unknown'}`}
    >
      {hasIndex && (
        <div className="relative h-32 w-32 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              innerRadius="70%"
              outerRadius="100%"
              barSize={12}
              data={data}
              startAngle={90}
              endAngle={-270}
            >
              {/* Pin the angular scale to 0-100 so the arc reflects the actual
                  percentage rather than auto-scaling to the single data point. */}
              <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
              <RadialBar
                background={{ fill: CHART.waterWash }}
                dataKey="value"
                cornerRadius={6}
                isAnimationActive={false}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-2xl font-semibold leading-none" style={{ color }}>
              {pct}%
            </span>
            <span className="microlabel mt-1">permeability</span>
          </div>
        </div>
      )}

      <dl className="grid w-full grid-cols-2 gap-x-4 gap-y-2 text-sm sm:flex-1">
        {permeabilityClass && (
          <Stat label="Permeability class" value={permeabilityClass} />
        )}
        {rechargeLabel && <Stat label="Recharge potential" value={rechargeLabel} />}
        {rechargeValue != null && (
          <Stat label="Recharge index" value={rechargeValue.toFixed(1)} mono />
        )}
        {netInfiltrationMm != null && (
          <Stat label="Net infiltration" value={`${netInfiltrationMm.toFixed(0)} mm`} mono />
        )}
      </dl>
    </figure>
  );
}

function Stat({ label, value, mono = false }) {
  return (
    <div>
      <dt className="microlabel">{label}</dt>
      <dd className={`mt-0.5 font-semibold capitalize ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  );
}
