import { useEffect, useState } from 'react';
import { listClientAssets, subscribeClientAssets, type ClientAssetRecord } from '../services/assetLibrary';

export function useClientAssets() {
  const [assets, setAssets] = useState<ClientAssetRecord[]>(() => listClientAssets());

  useEffect(() => {
    const sync = () => setAssets(listClientAssets());
    sync();
    return subscribeClientAssets(sync);
  }, []);

  return assets;
}

