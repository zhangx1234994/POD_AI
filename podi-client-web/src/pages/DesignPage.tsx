import ModuleWorkspacePage from '../components/ModuleWorkspacePage';
import { designTools } from '../config/clientCatalog';

export default function DesignPage() {
  return <ModuleWorkspacePage title="AI研发设计" subtitle="研发设计" items={designTools} mode="design" />;
}
