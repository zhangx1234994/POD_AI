import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { User, Mail, Lock, Edit2, Save } from 'lucide-react';
import { ACCOUNT_STATUS_UI_MAP, MEMBERSHIP_LEVEL_UI_MAP } from '@/constants/user';
import { normalizeAccountStatus, normalizeMembershipLevel } from '@/utils/userUtils';
import { UserInfo } from '@/types/user';

export interface ProfilePanelProps {
  userInfo: UserInfo | null;
  loading: boolean;
  isEditing: boolean;
  passwordData: { currentPassword: string; newPassword: string; confirmPassword: string };
  hasChanges: boolean;
  setUserInfo: (u: UserInfo | null) => void;
  setPasswordData: (p: { currentPassword: string; newPassword: string; confirmPassword: string }) => void;
  handleSaveProfile: () => Promise<void>;
  handleEditPassword: () => void;
  handleCancelPasswordEdit: () => void;
  handleSavePassword: () => Promise<void>;
}

export function ProfilePanel(props: ProfilePanelProps) {
  const {
    userInfo,
    loading,
    isEditing,
    passwordData,
    hasChanges,
    setUserInfo,
    setPasswordData,
    handleSaveProfile,
    handleEditPassword,
    handleCancelPasswordEdit,
    handleSavePassword,
  } = props;

  return (
    <div>
      {loading || !userInfo ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>基本信息</CardTitle>
                  <CardDescription className="text-xs">管理您的账号基本信息</CardDescription>
                </div>
                <Button size="sm" onClick={handleSaveProfile} disabled={!hasChanges}>
                  <Save className="w-4 h-4 mr-2" />
                  保存
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="username">用户名（不可修改）</Label>
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-muted-foreground" />
                  <Input id="username" value={userInfo?.username || ''} disabled placeholder="用户名" />
                </div>
                <p className="text-xs text-muted-foreground">注册时的用户名，无法修改</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="nickname">昵称</Label>
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-muted-foreground" />
                  <Input
                    id="nickname"
                    value={userInfo?.nickname || ''}
                    onChange={(e) => setUserInfo(userInfo ? { ...userInfo, nickname: e.target.value } : null)}
                    placeholder="输入昵称"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">邮箱地址（不可修改）</Label>
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-muted-foreground" />
                  <Input id="email" type="email" value={userInfo?.email || ''} disabled placeholder="邮箱地址" />
                </div>
                <p className="text-xs text-muted-foreground">注册时填写的邮箱地址，无法修改</p>
              </div>

              <Separator />

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>修改密码</Label>
                  {!isEditing ? (
                    <Button size="sm" variant="outline" onClick={handleEditPassword}>
                      <Edit2 className="w-4 h-4 mr-2" />
                      编辑
                    </Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={handleCancelPasswordEdit}>
                        取消
                      </Button>
                      <Button size="sm" onClick={handleSavePassword}>
                        <Save className="w-4 h-4 mr-2" />
                        保存
                      </Button>
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-muted-foreground" />
                    <Input
                      type="password"
                      placeholder="当前密码"
                      value={passwordData.currentPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                      disabled={!isEditing}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-muted-foreground" />
                    <Input
                      type="password"
                      placeholder="新密码"
                      value={passwordData.newPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                      disabled={!isEditing}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-muted-foreground" />
                    <Input
                      type="password"
                      placeholder="确认新密码"
                      value={passwordData.confirmPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                      disabled={!isEditing}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Right column: Account status */}
          <Card className="lg:col-span-1">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>账号状态</CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-muted-foreground">会员等级</div>
                  </div>
                  <div>
                    {(() => {
                      const rawMembership = (userInfo as any)?.membershipLevel || (userInfo as any)?.membership || userInfo?.role;
                      const key = normalizeMembershipLevel(rawMembership);
                      const entry = MEMBERSHIP_LEVEL_UI_MAP[key];
                      const Icon = entry.icon;
                      return (
                        <div className={`inline-flex items-center gap-2 px-2 py-1 rounded-md border ${entry.borderClass} ${entry.bgClass}`}>
                          <Icon className={`w-4 h-4 ${entry.textClass}`} />
                          <span className={`${entry.textClass} text-xs font-medium`}>{entry.label}</span>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                <Separator data-slot="separator-root" />

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-muted-foreground">加入时间</div>
                  </div>
                  <div className="inline-flex items-center gap-2 px-2 py-1 w-28">
                    <span className="text-xs text-foreground text-center">
                      {userInfo?.createdAt ? new Date(userInfo.createdAt).toLocaleDateString() : '-'}
                    </span>
                  </div>
                </div>

                <Separator data-slot="separator-root" />

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-muted-foreground">账号状态</div>
                  </div>
                  <div>
                    {(() => {
                      const raw = (userInfo as any)?.status || (userInfo as any)?.accountStatus || '';
                      const key = normalizeAccountStatus(raw);
                      const entry = ACCOUNT_STATUS_UI_MAP[key];
                      const Icon = entry.icon;
                      return (
                        <div className={`inline-flex items-center gap-2 px-2 py-1 rounded-md border ${entry.borderClass}`}>
                          <Icon className={`w-4 h-4 ${entry.textClass}`} />
                          <span className={`${entry.textClass} text-xs font-medium`}>{entry.label}</span>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ProfilePanel;
