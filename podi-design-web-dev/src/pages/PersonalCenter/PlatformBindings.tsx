import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Link2, CheckCircle2 } from 'lucide-react';

export interface PlatformBindingsProps {
  thirdPartyConnected: boolean;
  thirdPartyAccount: { username: string; apiKey: string };
  setThirdPartyAccount: (v: { username: string; apiKey: string }) => void;
  onConnectThirdParty: () => void;
  onDisconnectThirdParty: () => void;
};

export function PlatformBindings(props: PlatformBindingsProps) {
  const { thirdPartyConnected, thirdPartyAccount, setThirdPartyAccount, onConnectThirdParty, onDisconnectThirdParty } = props;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-md">
          <Link2 className="w-5 h-5" />
          第三方平台
        </CardTitle>
        <CardDescription className="text-xs">绑定第三方平台账号以访问外部图库</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-4">
            {thirdPartyConnected ? <span className="text-sm text-emerald-700">已绑定</span> : <span className="text-sm text-muted-foreground">未绑定</span>}
          </div>
          {thirdPartyConnected ? (
            <>
              <Alert className="border-green-500 bg-green-50">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <AlertDescription className="text-green-600">已成功绑定第三方账号</AlertDescription>
              </Alert>
              <div className="space-y-3 mt-6">
                <div className="flex items-center justify-between p-3 bg-muted rounded">
                  <span className="text-sm">账号名称</span>
                  <span className="text-sm font-medium">{thirdPartyAccount.username}</span>
                </div>
                <Button variant="destructive" className="w-full mt-4" onClick={onDisconnectThirdParty}>
                  解绑账号
                </Button>
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <div className="space-y-3">
                <Label htmlFor="thirdparty-username">用户名</Label>
                <Input
                  id="thirdparty-username"
                  placeholder="输入用户名"
                  value={thirdPartyAccount.username}
                  onChange={(e) => setThirdPartyAccount({ ...thirdPartyAccount, username: e.target.value })}
                />
              </div>
              <div className="mt-6 space-y-3">
                <Label htmlFor="thirdparty-apikey">API密钥</Label>
                <Input
                  id="thirdparty-apikey"
                  type="password"
                  placeholder="输入API密钥"
                  value={thirdPartyAccount.apiKey}
                  onChange={(e) => setThirdPartyAccount({ ...thirdPartyAccount, apiKey: e.target.value })}
                />
              </div>
              <Button className="w-full mt-4" onClick={onConnectThirdParty} disabled={!thirdPartyAccount.username || !thirdPartyAccount.apiKey}>
                <Link2 className="w-4 h-4 mr-2" />
                绑定账号
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default PlatformBindings;
