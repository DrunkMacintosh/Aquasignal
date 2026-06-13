// Compact 24-month history line. Quiet by design: no axes, just the shape of
// the timeline plus the latest reading as a colour-coded figure.
import { Line, LineChart, ReferenceLine, ResponsiveContainer } from 'recharts';
import { CRITICAL_THRESHOLD, formatMonth, riskBand } from '../lib/risk.js';
import { ChartSkeleton } from './Skeletons.jsx';

export default function Sparkline({ points, isLoading }) {
  if (isLoading) return <ChartSkeleton height={72} />;
  if (!points?.length) {
    return <p className="text-sm text-ink-soft">No historical scores for this district yet.</p>;
  }

  const latest = points[points.length - 1];
  const band = riskBand(latest.risk);

  return (
    <div
      className="flex items-center gap-4"
      aria-label={`Risk history, ${points.length} months. Latest: ${latest.risk.toFixed(0)} out of 100 in ${formatMonth(latest.month)}.`}
    >
      <div className="h-[64px] min-w-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 6, right: 4, bottom: 6, left: 4 }}>
            <ReferenceLine y={CRITICAL_THRESHOLD} stroke="#B71C1C" strokeOpacity={0.35} strokeDasharray="3 3" />
            <Line
              dataKey="risk"
              stroke="#1C2B33"
              strokeWidth={1.75}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="shrink-0 text-right">
        <p className="font-mono text-2xl font-semibold leading-none" style={{ color: band.level === 'medium' ? '#7A5800' : band.color }}>
          {latest.risk.toFixed(0)}
        </p>
        <p className="microlabel mt-1">{formatMonth(latest.month)}</p>
      </div>
    </div>
  );
}
