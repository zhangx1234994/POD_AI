import { LoginGate } from './components/LoginGate';
import { IntegrationDashboard } from './pages/IntegrationDashboard';

function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <LoginGate>
        <IntegrationDashboard />
      </LoginGate>
    </div>
  );
}

export default App;
