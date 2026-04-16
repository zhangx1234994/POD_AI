// Compatibility shim.
// New code should import from `src/config/clientCatalog.ts` or `src/config/clientDemoData.ts`.

export {
  designTools,
  navItems,
  roleCases,
  shootTools,
  shortcuts,
  studioAgents,
  toolboxTools,
} from '../config/clientCatalog';

export {
  demoRecentAssets as recentAssets,
  demoRecentTasks as recentTasks,
  demoWalletLedger as walletLedger,
  demoWalletPacks as walletPacks,
  demoWhiteboardProjects as whiteboardProjects,
} from '../config/clientDemoData';
