import React, { useState, useEffect } from 'react';
import AppLayout from './components/layout/AppLayout';
import AdminDashboard from './components/admin/AdminDashboard';

export default function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  if (path === '/admin') {
    return <AdminDashboard onClose={() => window.location.href = '/'} />;
  }

  return <AppLayout />;
}
