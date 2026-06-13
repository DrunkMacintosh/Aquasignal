// Alert subscription toggle + threshold slider for one district. Uses the
// per-district unsubscribe endpoint; the local mirror (lib/subscriptions.js)
// exists only because the API has no "list my subscriptions" yet.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { subscribeAlert, unsubscribeDistrict } from '../api/client.js';
import { useAuth } from '../context/AuthContext.jsx';
import { riskBand } from '../lib/risk.js';
import { removeSubscription, setSubscription, useSubscriptions } from '../lib/subscriptions.js';

const DEFAULT_THRESHOLD = 75;

export default function AlertSubscribe({ district }) {
  const { isAuthenticated, promptSignIn } = useAuth();
  const subscriptions = useSubscriptions();
  const savedThreshold = subscriptions[district];
  const isSubscribed = savedThreshold !== undefined;
  const [threshold, setThreshold] = useState(savedThreshold ?? DEFAULT_THRESHOLD);
  const band = riskBand(threshold);

  const toggle = useMutation({
    mutationFn: async (enable) => {
      if (enable) {
        await subscribeAlert(district, threshold);
        setSubscription(district, threshold);
        return;
      }
      try {
        await unsubscribeDistrict(district);
      } catch (error) {
        // 404 = the server already has no such subscription; treat the local
        // mirror as stale and fall through to correcting it.
        if (error?.response?.status !== 404) throw error;
      }
      removeSubscription(district);
    },
  });

  const sliderId = `alert-threshold-${district.replace(/\W+/g, '-')}`;

  // Viewing the data is open to everyone; only setting an alert needs an
  // account. Anonymous visitors get a sign-in prompt in place of the toggle.
  if (!isAuthenticated) {
    return (
      <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
        <p className="text-sm font-semibold">Get alerts for {district}</p>
        <p className="mt-1 text-xs text-ink-soft">
          Sign in to be notified when this district's risk crosses a threshold you choose.
        </p>
        <button
          type="button"
          onClick={promptSignIn}
          className="btn-primary mt-3 w-full !py-2 text-sm"
        >
          Sign in to set alerts
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={sliderId} className="text-sm font-semibold">
          Alert me when risk exceeds{' '}
          <output
            className="rounded px-1.5 py-0.5 font-mono font-semibold"
            style={{ backgroundColor: band.color, color: band.onColor }}
          >
            {threshold}
          </output>
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={isSubscribed}
          aria-label={`Alerts for ${district}: ${isSubscribed ? 'on' : 'off'}`}
          disabled={toggle.isPending}
          onClick={() => toggle.mutate(!isSubscribed)}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
            isSubscribed ? 'bg-water' : 'bg-ink/20'
          }`}
        >
          <span
            aria-hidden="true"
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
              isSubscribed ? 'left-[22px]' : 'left-0.5'
            }`}
          />
        </button>
      </div>
      <input
        id={sliderId}
        type="range"
        min="0"
        max="100"
        step="5"
        value={threshold}
        disabled={isSubscribed || toggle.isPending}
        onChange={(event) => setThreshold(Number(event.target.value))}
        className="mt-3 w-full accent-water disabled:opacity-50"
        aria-valuetext={`${threshold} out of 100 (${band.label})`}
      />
      <p className="mt-1.5 text-xs text-ink-soft">
        {isSubscribed
          ? `You'll be notified when ${district}'s risk reaches ${savedThreshold}. Turn off to change the threshold.`
          : 'Pick a threshold, then switch alerts on.'}
      </p>
      {toggle.isError && (
        <p role="alert" className="mt-1.5 text-xs font-medium text-risk-critical">
          Could not update the subscription — please try again.
        </p>
      )}
    </div>
  );
}
