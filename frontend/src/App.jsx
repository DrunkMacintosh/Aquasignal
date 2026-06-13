import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import LoginPage from './pages/LoginPage.jsx';
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
        <Shell />
      </AuthProvider>
    </QueryClientProvider>
  );
}

function Shell() {
  const { isAuthenticated } = useAuth();

  // Drop all cached API data on sign-out so nothing leaks into the next
  // session on a shared machine.
  useEffect(() => {
    if (!isAuthenticated) queryClient.clear();
  }, [isAuthenticated]);

  return isAuthenticated ? <MapPage /> : <LoginPage />;
}
