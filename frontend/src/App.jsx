import { useEffect, useRef } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import WarmupBanner from './components/WarmupBanner.jsx';
import AuthModal from './components/auth/AuthModal.jsx';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import MapPage from './pages/MapPage.jsx';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WarmupBanner />
        <Shell />
      </AuthProvider>
    </QueryClientProvider>
  );
}

function Shell() {
  const { isAuthenticated, isPromptOpen, closePrompt } = useAuth();
  const wasAuthenticated = useRef(isAuthenticated);

  // Drop cached API data only on an actual sign-out (authenticated -> not), so
  // a per-user view never lingers on a shared machine. We deliberately do NOT
  // clear on the initial anonymous load — that would wipe freshly fetched
  // public map data on first paint.
  useEffect(() => {
    if (wasAuthenticated.current && !isAuthenticated) queryClient.clear();
    wasAuthenticated.current = isAuthenticated;
  }, [isAuthenticated]);

  return (
    <>
      <MapPage />
      {isPromptOpen && <AuthModal onClose={closePrompt} />}
    </>
  );
}
