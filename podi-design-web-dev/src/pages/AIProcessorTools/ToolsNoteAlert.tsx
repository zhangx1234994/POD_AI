import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';

interface Props {
  note: string;
};

export function ToolsNoteAlert({ note }: Props) {
  if (!note) return null;

  return (
    <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
      <Info className="w-4 h-4 text-blue-600" />
      <AlertDescription className="text-sm text-blue-600 dark:text-blue-400">{note}</AlertDescription>
    </Alert>
  );
};

export default ToolsNoteAlert;
