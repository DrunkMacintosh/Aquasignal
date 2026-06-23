import { useState } from 'react';
import { useCriticalDistricts } from '../api/hooks.js';
import Banner from './ui/Banner.jsx';

/**
 * Persistent banner shown while any subscribed district sits in the critical
 * band. District names open the detail panel directly.
 */
export default function AlertBanner({ onOpenDistrict }) {
  const { critical } = useCriticalDistricts();
  const [dismissed, setDismissed] = useState(false);

  if (critical.length === 0 || dismissed) return null;

  return (
    <Banner
      tone="critical"
      icon="⚠"
      onDismiss={() => setDismissed(true)}
      dismissLabel="Dismiss critical risk banner"
      className="flex-wrap gap-x-3 gap-y-1"
    >
      <span className="mr-2 text-[11px] font-semibold tracking-[0.01em]">
        Critical risk
      </span>
      <span className="text-sm">
        {critical.length === 1
          ? 'This province or city needs attention:'
          : 'These provinces and cities need attention:'}
      </span>
      <span className="ml-2 inline-flex flex-wrap gap-1.5">
        {critical.map((district) => (
          <button
            key={district}
            type="button"
            onClick={() => onOpenDistrict(district)}
            aria-label={`Open ${district} details`}
            className="rounded-md bg-white/15 px-2.5 py-0.5 text-sm font-semibold transition-colors hover:bg-white/30 focus-visible:outline-white"
          >
            {district}
          </button>
        ))}
      </span>
    </Banner>
  );
}
