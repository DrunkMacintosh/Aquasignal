// Session holder. The JWT lives ONLY in React state + the axios module — a
// page refresh deliberately costs a re-login. Storing it in localStorage
// would let any XSS payload (or anyone at a shared office computer) read a
// 24-hour credential at rest; in-memory tokens disappear when the tab closes.
// The robust long-term fix is an httpOnly cookie session, which needs backend
// support — until then this is the safest client-side option.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  login as apiLogin,
  register as apiRegister,
  refreshToken,
  setAccessToken,
  setUnauthorizedHandler,
} from '../api/client.js';

const REFRESH_MARGIN_MS = 5 * 60_000; // renew 5 minutes before expiry

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null); // { email, expiresAt }
  const [isExpiring, setIsExpiring] = useState(false);
  // Browsing AquaSignal needs no account; this flag drives the sign-in modal,
  // which we only raise when a visitor chooses to set an alert (or taps the
  // header's "Sign in"). State lives here so any component can trigger it
  // without prop-drilling; App renders the modal itself (avoids a cycle).
  const [isPromptOpen, setIsPromptOpen] = useState(false);
  const timersRef = useRef([]);

  const promptSignIn = useCallback(() => setIsPromptOpen(true), []);
  const closePrompt = useCallback(() => setIsPromptOpen(false), []);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const signOut = useCallback(() => {
    clearTimers();
    setAccessToken(null);
    setIsExpiring(false);
    setSession(null);
  }, [clearTimers]);

  const applySession = useCallback(
    (email, tokenResponse) => {
      const expiresAt = Date.now() + tokenResponse.expires_in * 1000;
      setAccessToken(tokenResponse.access_token);
      setSession({ email, expiresAt });
      setIsExpiring(false);

      clearTimers();
      const refreshIn = Math.max(expiresAt - Date.now() - REFRESH_MARGIN_MS, 5_000);
      timersRef.current.push(
        setTimeout(async () => {
          try {
            applySession(email, await refreshToken());
          } catch {
            // Refresh failed (offline, server down): warn now, end the
            // session at actual expiry instead of dying mid-request.
            setIsExpiring(true);
            timersRef.current.push(
              setTimeout(signOut, Math.max(expiresAt - Date.now(), 0)),
            );
          }
        }, refreshIn),
      );
    },
    [clearTimers, signOut],
  );

  const signIn = useCallback(
    async (email, password) => {
      applySession(email, await apiLogin(email, password));
    },
    [applySession],
  );

  // /auth/register returns the same TokenResponse as login, so a new account
  // lands on the map signed in — no second form.
  const signUp = useCallback(
    async (email, password, fullName) => {
      applySession(email, await apiRegister(email, password, fullName));
    },
    [applySession],
  );

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => {
      setUnauthorizedHandler(null);
      clearTimers();
    };
  }, [signOut, clearTimers]);

  // A successful sign-in/registration ends the prompt — the visitor lands back
  // on whatever they were doing (e.g. the same district's alert toggle).
  useEffect(() => {
    if (session) setIsPromptOpen(false);
  }, [session]);

  const value = useMemo(
    () => ({
      isAuthenticated: session !== null,
      email: session?.email ?? null,
      expiresAt: session?.expiresAt ?? null,
      isExpiring,
      isPromptOpen,
      promptSignIn,
      closePrompt,
      signIn,
      signUp,
      signOut,
    }),
    [session, isExpiring, isPromptOpen, promptSignIn, closePrompt, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
