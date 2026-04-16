import ModuleWorkspacePage from '../components/ModuleWorkspacePage';
import { toolboxTools } from '../config/clientCatalog';

export default function ToolboxPage() {
  return <ModuleWorkspacePage title="AI工具箱" subtitle="图像处理" items={toolboxTools} mode="toolbox" />;
}
