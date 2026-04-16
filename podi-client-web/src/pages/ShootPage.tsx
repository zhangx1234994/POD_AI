import ModuleWorkspacePage from '../components/ModuleWorkspacePage';
import { shootTools } from '../config/clientCatalog';

export default function ShootPage() {
  return <ModuleWorkspacePage title="AI视觉商拍" subtitle="视觉商拍" items={shootTools} mode="shoot" />;
}
