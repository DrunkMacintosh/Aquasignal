// Centered dialog that hosts the auth forms. Opened from the "Sign in" button
// in the map header and from the alert toggle when a visitor isn't signed in.
// AuthContext closes it automatically once a session exists; this component
// owns only the overlay, escape/backdrop dismissal, and initial focus.
import { useEffect, useRef } from 'react';
import AuthForms from './AuthForms.jsx';

export default function AuthModal({ onClose }) {
  const panelRef = useRef(null);

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    // Pull focus into the dialog for keyboard and screen-reader users.
    panelRef.current?.querySelector('input, button')?.focus();
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/50 p-4 backdrop-blur-sm animate-fade-up"
      // mousedown (not click) so a text drag that ends on the backdrop never
      // dismisses; only a true backdrop press closes.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Sign in to AquaSignal"
        className="card corner-ticks relative max-h-[90vh] w-full max-w-sm overflow-y-auto p-6"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-md px-2 py-1 text-lg leading-none text-ink-soft transition-colors hover:bg-paper hover:text-ink"
        >
          ×
        </button>
        <AuthForms />
      </div>
    </div>
  );
}
