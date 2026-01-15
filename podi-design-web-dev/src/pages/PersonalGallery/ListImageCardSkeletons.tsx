import React from 'react';
import { Card } from '@/components/ui/card';

export interface ListImageCardSkeletonsProps {
  count?: number;
  placeholderSrc?: string;
}

export const ListImageCardSkeletons: React.FC<ListImageCardSkeletonsProps> = ({ count = 3, placeholderSrc }) => {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={`ls-${i}`} className="mb-3">
          <div>
            <Card className="relative overflow-hidden">
              <div className="p-4">
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 flex-shrink-0 rounded overflow-hidden bg-muted">
                    <img src={placeholderSrc} alt="placeholder" className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="mb-2">
                      <div className="h-4 bg-muted/20 rounded w-1/2 animate-pulse" />
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="h-3 bg-muted/20 rounded w-1/4 animate-pulse" />
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      ))}
    </>
  );
};

export default ListImageCardSkeletons;
