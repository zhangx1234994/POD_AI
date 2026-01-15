import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export interface SecuritySettingProps {
  onEnable2FA?: (enabled: boolean) => void;
  onToggleLoginNotices?: (enabled: boolean) => void;
  onViewActivityLog?: () => void;
}

export function SecuritySetting(props: SecuritySettingProps) {
  const { onEnable2FA, onToggleLoginNotices, onViewActivityLog } = props;
  const [twoFAEnabled, setTwoFAEnabled] = useState(true);
  const [loginNoticesEnabled, setLoginNoticesEnabled] = useState(true);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>安全设置</CardTitle>
          <CardDescription>管理您的账号安全选项</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="space-y-1">
              <h4 className="font-medium">两步验证</h4>
              <p className="text-sm text-muted-foreground">为您的账号添加额外的安全保护</p>
            </div>
            <Button
              variant="outline"
              className={twoFAEnabled ? 'bg-blue-500 text-white border-blue/30 hover:bg-white/20' : ''}
              onClick={() => {
                setTwoFAEnabled(!twoFAEnabled);
                onEnable2FA?.(!twoFAEnabled);
              }}
            >
              {twoFAEnabled ? '已启用' : '启用'}
            </Button>
          </div>

          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="space-y-1">
              <h4 className="font-medium">登录通知</h4>
              <p className="text-sm text-muted-foreground">在新设备登录时接收邮件通知</p>
            </div>
            <Button
              variant="outline"
              className={loginNoticesEnabled ? 'bg-blue-500 text-white border-blue/30 hover:bg-white/20' : ''}
              onClick={() => {
                setLoginNoticesEnabled(!loginNoticesEnabled);
                onToggleLoginNotices?.(!loginNoticesEnabled);
              }}
            >
              {loginNoticesEnabled ? '已启用' : '启用'}
            </Button>
          </div>

          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="space-y-1">
              <h4 className="font-medium">活动日志</h4>
              <p className="text-sm text-muted-foreground">查看最近的账号活动记录</p>
            </div>
            <Button variant="outline" onClick={() => onViewActivityLog?.()}>查看</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SecuritySetting;
