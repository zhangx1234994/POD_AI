import { useLayoutEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import ClientPromoStrip from '../components/ClientPromoStrip';
import TopNav from '../components/TopNav';

export default function ClientLayout() {
  const shellRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    shellRef.current?.focus();
  }, []);

  return (
    <div ref={shellRef} className="client-app-shell" tabIndex={-1}>
      <div className="client-app-shell__backdrop" />
      <ClientPromoStrip />
      <TopNav />
      <main className="client-main">
        <Outlet />
      </main>
    </div>
  );
}
