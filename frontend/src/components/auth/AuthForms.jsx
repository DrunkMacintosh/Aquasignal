// Sign-in / registration forms, extracted from the old full-page LoginPage so
// they can live inside the AuthModal. One card, two modes — registering signs
// the new account straight in (the backend returns the same TokenResponse as
// login). Browsing AquaSignal needs no account; these forms appear only when a
// visitor chooses to set an alert or taps "Sign in".
import { useState } from 'react';
import { useAuth } from '../../context/AuthContext.jsx';
import { PASSWORD_MIN_CHARS, passwordIssue } from '../../lib/validation.js';

export default function AuthForms() {
  const [mode, setMode] = useState('signin'); // 'signin' | 'register'
  return mode === 'signin' ? (
    <SignInForm onSwitch={() => setMode('register')} />
  ) : (
    <RegisterForm onSwitch={() => setMode('signin')} />
  );
}

function SignInForm({ onSwitch }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(signInErrorMessage(err));
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Sign in"
      subtitle="Sign in to set up and manage province and city alerts."
      switchPrompt="New here?"
      switchLabel="Create an account"
      onSwitch={onSwitch}
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field
          id="signin-email"
          label="Work email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        <Field
          id="signin-password"
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
        />
        <FormError message={error} />
        <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthCard>
  );
}

function RegisterForm({ onSwitch }) {
  const { signUp } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const issue = passwordIssue(password, confirm);
    if (issue) {
      setError(issue);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await signUp(email, password, fullName.trim());
    } catch (err) {
      setError(registerErrorMessage(err));
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Access starts as field officer; an administrator can raise it later."
      switchPrompt="Already have an account?"
      switchLabel="Sign in"
      onSwitch={onSwitch}
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field
          id="register-name"
          label="Full name (optional)"
          type="text"
          autoComplete="name"
          value={fullName}
          onChange={setFullName}
        />
        <Field
          id="register-email"
          label="Work email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        <Field
          id="register-password"
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          hint={`At least ${PASSWORD_MIN_CHARS} characters.`}
        />
        <Field
          id="register-confirm"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={setConfirm}
        />
        <FormError message={error} />
        <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthCard>
  );
}

function AuthCard({ title, subtitle, switchPrompt, switchLabel, onSwitch, children }) {
  return (
    <div className="w-full">
      <header className="mb-6">
        <BrandMark />
      </header>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1.5 text-sm text-ink-soft">{subtitle}</p>
      <div className="mt-6">{children}</div>
      <p className="mt-5 text-sm text-ink-soft">
        {switchPrompt}{' '}
        <button
          type="button"
          onClick={onSwitch}
          className="font-semibold text-water underline-offset-2 hover:underline"
        >
          {switchLabel}
        </button>
      </p>
      <p className="mt-5 border-t border-ink/10 pt-4 text-xs leading-relaxed text-ink-soft">
        For your security, your session is held in memory only — it ends when this tab
        closes or reloads, and you simply sign in again.
      </p>
    </div>
  );
}

function Field({ id, label, type, autoComplete, value, onChange, hint }) {
  return (
    <div>
      <label htmlFor={id} className="microlabel">
        {label}
      </label>
      <input
        id={id}
        type={type}
        required={type !== 'text'}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="mt-1.5 w-full rounded-lg border border-ink/15 bg-surface px-3.5 py-2.5 text-sm focus-visible:outline-water"
      />
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-ink-faint">
          {hint}
        </p>
      )}
    </div>
  );
}

function FormError({ message }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-lg border border-risk-critical/30 bg-risk-critical/5 px-3.5 py-2.5 text-sm font-medium text-risk-critical"
    >
      {message}
    </p>
  );
}

function signInErrorMessage(err) {
  const status = err?.response?.status;
  if (status === 401) return 'Invalid email or password.';
  if (status === 429) return 'Too many attempts — please wait a minute and try again.';
  if (status === 422) return 'Please enter a valid email address and password.';
  return 'Cannot reach the AquaSignal server. Check your connection and try again.';
}

function registerErrorMessage(err) {
  const status = err?.response?.status;
  if (status === 409) return 'An account with this email already exists — try signing in.';
  if (status === 422) return 'Please check the email address and password requirements.';
  if (status === 429) return 'Too many attempts — please wait a minute and try again.';
  // A reachable server without the route means it's running pre-registration
  // code — seen when the backend wasn't restarted after deployment.
  if (status === 404) {
    return 'The server does not support registration yet — ask IT to update and restart the AquaSignal backend.';
  }
  return 'Cannot reach the AquaSignal server. Check your connection and try again.';
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
        <path d="M16 3c5 7 9 11.5 9 17a9 9 0 1 1-18 0c0-5.5 4-10 9-17z" fill="#0E6E83" />
      </svg>
      <span className="font-display text-xl font-bold">AquaSignal</span>
    </div>
  );
}
