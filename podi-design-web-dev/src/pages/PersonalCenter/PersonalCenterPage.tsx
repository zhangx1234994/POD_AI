import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { userAPI } from '@/services/userAPI';
import { USER_CENTER_TABS, DEFAULT_USER_INFO } from '@/constants/user';
import { UserInfo } from '@/types/user';
import { ProfilePanel } from './ProfilePanel';
import { UsageStats } from './UsageStats';

export function PersonalCenterPage() {
  const [loading, setLoading] = useState(true);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [stats, setStats] = useState<{
    uploadedImages: number;
    generatedImages: number;
    totalProcessed: number;
    todayUsage: number;
    monthlyLimit: number;
    storageUsed: number;
    storageLimit: number;
  } | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);

  const [originalUserInfo, setOriginalUserInfo] = useState<UserInfo | null>(null);

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const hasChanges: boolean = !!(
    userInfo &&
    originalUserInfo &&
    JSON.stringify(userInfo) !== JSON.stringify(originalUserInfo)
  );

  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        const data = await userAPI.getCurrentUser();
        if (data) {
          setUserInfo(data);
          setOriginalUserInfo(data);
        } else {
          setUserInfo(DEFAULT_USER_INFO);
          setOriginalUserInfo(DEFAULT_USER_INFO);
        }
      } catch (error) {
        console.error('Failed to fetch user info:', error);
        toast.error('获取用户信息失败');
        setUserInfo(DEFAULT_USER_INFO);
        setOriginalUserInfo(DEFAULT_USER_INFO);
      } finally {
        setLoading(false);
      }
    };

    fetchUserInfo();
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      if (activeTab === 'usageStats' && userInfo && userInfo.user_id && !stats) {
        setStatsLoading(true);
        try {
          const usageStats = await userAPI.getUsageStatistics(userInfo.user_id);
          if (usageStats) {
            setStats(usageStats);
          }
        } catch (error) {
          console.error('Failed to fetch usage stats:', error);
          toast.error('获取使用统计数据失败');
        } finally {
          setStatsLoading(false);
        }
      }
    };

    fetchStats();
  }, [activeTab, userInfo, stats]);

  const handleSaveProfile = async () => {
    try {
      if (!userInfo) return;

      const nickname = userInfo.nickname ?? '';
      if (!nickname) {
        toast.error('昵称不能为空');
        return;
      }
      const updatedUserInfo = await userAPI.updateNickname(nickname);
      if (updatedUserInfo) {
        setUserInfo(updatedUserInfo);
        setOriginalUserInfo(updatedUserInfo);
        toast.success('个人资料更新成功');
      } else {
        setUserInfo({ ...userInfo, nickname });
        setOriginalUserInfo({ ...userInfo, nickname });
        toast.success('昵称更新成功');
      }
    } catch (error) {
      console.error('Failed to update user info:', error);
      toast.error('更新失败，请重试');
    }
  };

  const handleEditPassword = () => {
    setIsEditing(true);
  };

  const handleCancelPasswordEdit = () => {
    setIsEditing(false);
    setPasswordData({
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    });
  };

  const handleSavePassword = async () => {
    if (!passwordData.newPassword) {
      toast.error('请输入新密码');
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      toast.error('两次输入的密码不一致');
      return;
    }

    try {
      await userAPI.updatePassword(passwordData.currentPassword, passwordData.newPassword);

      toast.success('密码更新成功');
      handleCancelPasswordEdit();
    } catch (error) {
      console.error('Failed to update password:', error);
      toast.error('密码更新失败，请重试');
    }
  };

  return (
    <div className="p-6 bg-gradient-to-br from-background via-background to-muted/20">
      <div>
        <h1 className="text-2xl font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">个人中心</h1>
        <p className="text-muted-foreground text-sm mt-1">管理您的账号信息和第三方平台绑定</p>
      </div>

      {loading || !userInfo ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="profile" value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            {USER_CENTER_TABS.map((t) => (
              t.value !== 'linkedPlatforms' && t.value !== 'securitySettings' && (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                </TabsTrigger>
              )
            ))}
          </TabsList>
          <TabsContent value="profile">
            <ProfilePanel
              userInfo={userInfo}
              loading={loading}
              isEditing={isEditing}
              passwordData={passwordData}
              hasChanges={hasChanges}
              setUserInfo={setUserInfo}
              setPasswordData={setPasswordData}
              handleSaveProfile={handleSaveProfile}
              handleEditPassword={handleEditPassword}
              handleCancelPasswordEdit={handleCancelPasswordEdit}
              handleSavePassword={handleSavePassword}
            />
          </TabsContent>
          <TabsContent value="usageStats" className="space-y-4">
            {statsLoading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : stats ? (
              <UsageStats stats={stats} />
            ) : (
              <div className="text-center py-8 text-muted-foreground">加载统计数据中...</div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

export default PersonalCenterPage;
