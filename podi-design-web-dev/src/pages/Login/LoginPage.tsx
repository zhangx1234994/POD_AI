import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { authAPI, getFixedSmsCode } from '@/utils/http';
import { toast } from 'sonner';
import { LoginContent } from './LoginContent';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Eye, EyeOff } from 'lucide-react';

export function LoginPage({ onSuccess }: { onSuccess?: () => void; }) {
  const fixedSmsCode = getFixedSmsCode();
  const [phone, setPhone] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState<'phone' | 'username'>('phone');
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const countdownRef = useRef<number | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const { login, loginPhone, checkAuth } = useAuth();
  const navigate = useNavigate();

  const startCountdown = (seconds: number) => {
    if (countdownRef.current) {
      window.clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    setCountdown(seconds);
    setSendingCode(false);
    const expireTime = Date.now() + seconds * 1000;
    try {
      localStorage.setItem('smsExpireTime', String(expireTime));
    } catch (err) {
      // ignore storage errors
    }
    countdownRef.current = window.setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          if (countdownRef.current) {
            window.clearInterval(countdownRef.current as number);
            countdownRef.current = null;
          }
          try { localStorage.removeItem('smsExpireTime'); } catch (e) {}
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const handlePhoneChange = (e: any) => {
    const v = e.target.value;
    setPhone(v);
    if (!v.trim()) {
      setFieldErrors((prev) => ({ ...prev, phone: '手机号不能为空' }));
    } else if (!validatePhone(v)) {
      setFieldErrors((prev) => ({ ...prev, phone: '请输入正确的手机号码' }));
    } else {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.phone;
        return next;
      });
    }
    setError(null);
    setErrorStatus(null);
    if (countdown > 0) resetCountdown();
  };

  useEffect(() => {
    const expire = Number(localStorage.getItem('smsExpireTime') || '0');
    const now = Date.now();
    if (expire && expire > now) {
      const remaining = Math.ceil((expire - now) / 1000);
      startCountdown(remaining);
    }

    return () => {
      if (countdownRef.current) {
        window.clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    };
  }, []);

  const validatePhone = (p: string) => {
    const v = p.replace(/\s+/g, '');
    return /^1[3-9]\d{9}$/.test(v);
  };

  const resetCountdown = () => {
    if (countdownRef.current) {
      window.clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    setCountdown(0);
    setSendingCode(false);
    try {
      localStorage.removeItem('smsExpireTime');
    } catch (e) {
      // ignore
    }
  };

  const handleVerifyCodeChange = (e: any) => {
    const v = e.target.value.replace(/\D/g, '');
    setVerifyCode(v);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.verifyCode;
      return next;
    });
    setError(null);
    setErrorStatus(null);
  };

  const handleUsernameChange = (e: any) => {
    const v = e.target.value;
    setUsername(v);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.username;
      return next;
    });
    setError(null);
    setErrorStatus(null);
  };

  const handlePasswordChange = (e: any) => {
    const v = e.target.value;
    setPassword(v);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.password;
      return next;
    });
    setError(null);
    setErrorStatus(null);
  };

  const handleSendCode = async () => {
    if (countdown > 0) return;
    setFieldErrors({});
    setError(null);
    setErrorStatus(null);
    const errors: Record<string, string> = {};
    if (!phone.trim()) {
      errors.phone = '手机号不能为空';
    } else if (!/^\d{6,15}$/.test(phone.replace(/\s+/g, ''))) {
      errors.phone = '手机号格式不正确';
    }

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    try {
      setSendingCode(true);
      await authAPI.sendSms(phone, 'login');
      if (fixedSmsCode) {
        setVerifyCode(fixedSmsCode);
        toast.success(`已启用测试验证码：${fixedSmsCode}`);
      } else {
        toast.success('验证码已发送，5分钟内有效。');
      }
      startCountdown(60);
    } catch (err: any) {
      setSendingCode(false);
      const data = err?.response?.data;
      const msg = err?.friendlyMessage || data?.message || err?.message || '发送验证码失败';
      if (data?.details && typeof data.details === 'object') {
        setFieldErrors((prev) => ({ ...prev, ...data.details }));
      }
      setError(msg);
      setErrorStatus(err?.response?.status || null);
    }
  };

  const handleLogin = async () => {
    setFieldErrors({});
    setError(null);
    setErrorStatus(null);

    const errors: Record<string, string> = {};
    if (activeTab === 'phone') {
      if (!phone.trim()) {
        errors.phone = '手机号不能为空';
      } else if (!/^\d{6,15}$/.test(phone.replace(/\s+/g, ''))) {
        errors.phone = '手机号格式不正确';
      }
      if (!verifyCode.trim()) {
        errors.verifyCode = '请输入验证码';
      } else if (!/^\d+$/.test(verifyCode)) {
        errors.verifyCode = '验证码必须为数字';
      }
    } else {
      if (!username.trim()) errors.username = '用户名不能为空';
      if (!password.trim()) errors.password = '密码不能为空';
    }

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    try {
      if (activeTab === 'phone') {
        await loginPhone(phone, verifyCode, true);
        try {
          await checkAuth();
        } catch (e) {
          // ignore
        }
      } else {
        await login(username, password);
      }
      if (typeof onSuccess === 'function') onSuccess();
    } catch (e: any) {
      const data = e?.response?.data;
      const userFriendlyMessage = e?.friendlyMessage || data?.message || e?.message || '登录失败';
      if (data?.details && typeof data.details === 'object') {
        setFieldErrors((prev) => ({ ...prev, ...data.details }));
      }
      setError(userFriendlyMessage);
      setErrorStatus(e?.response?.status || null);
    } finally {
      setLoading(false);
    }
  };

  const currentYear = new Date().getFullYear();
  const showGlobalError = Boolean(error && (Object.keys(fieldErrors).length === 0 || errorStatus === 500 || errorStatus === 401));

  return (
    <div className="min-h-screen flex bg-white dark:bg-gray-950">
      <div className="w-full lg:w-1/2 flex flex-col">
        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <Card className="shadow-2xl bg-white border-0 w-full max-w-md">
            <CardHeader className="space-y-2 pb-2 px-0 pt-0">
              <CardTitle className="text-3xl font-semibold flex items-center gap-2">
                <span className="inline-block text-4xl">👋</span>欢迎
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 px-0 [&:last-child]:pb-0">
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'phone' | 'username')}>
                <TabsList className="w-full rounded-full p-1 shadow-sm">
                    <TabsTrigger
                      value="phone"
                      className="w-1/2 py-2 text-sm"
                    >
                      手机号登录
                    </TabsTrigger>
                    <TabsTrigger
                      value="username"
                      className="w-1/2 py-2 text-sm font-medium"
                    >
                      用户名登录
                    </TabsTrigger>
                  </TabsList>

                <TabsContent value="phone" className="flex-1 outline-none space-y-4 mt-6">
                  <div className="space-y-3">
                    <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">
                      手机号
                    </label>
                    <Input
                      value={phone}
                      onChange={handlePhoneChange}
                      placeholder="请输入手机号"
                      className="bg-white border-gray-200 transition-all duration-300 placeholder:text-gray-400 focus:cursor-text focus:border-primary/50 hover:border-primary/50"
                    />
                    {fieldErrors.phone && <p className="text-xs text-red-600 mt-1">{fieldErrors.phone}</p>}
                  </div>

                  <div className="space-y-3">
                    <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">
                      验证码
                    </label>
                    <div className="flex items-center gap-2">
                      <Input
                        value={verifyCode}
                        onChange={handleVerifyCodeChange}
                        placeholder="请输入验证码"
                        className="bg-white border-gray-200 transition-all duration-300 placeholder:text-gray-400 focus:cursor-text focus:border-primary/50 hover:border-primary/50"
                      />
                      <Button
                        onClick={handleSendCode}
                        disabled={!validatePhone(phone) || sendingCode || countdown > 0}
                        className="inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2"
                      >
                        {countdown > 0 ? `${countdown}秒后重试` : sendingCode ? '发送中...' : '发送验证码'}
                      </Button>
                    </div>
                    {fieldErrors.verifyCode && <p className="text-xs text-red-600 mt-1">{fieldErrors.verifyCode}</p>}
                  </div>
                </TabsContent>

                <TabsContent value="username" className="flex-1 outline-none space-y-4 mt-6">
                  <div className="space-y-3">
                    <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">
                      用户名
                    </label>
                      <Input
                        value={username}
                        onChange={handleUsernameChange}
                        placeholder="请输入用户名"
                        className="bg-white border-gray-200 transition-all duration-300 placeholder:text-gray-400 focus:cursor-text focus:border-primary/50 hover:border-primary/50"
                      />
                    {fieldErrors.username && <p className="text-xs text-red-600 mt-1">{fieldErrors.username}</p>}
                  </div>

                  <div className="space-y-3">
                    <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">
                      密码
                    </label>
                    <div className="relative">
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={handlePasswordChange}
                        placeholder="请输入密码"
                        className="bg-white border-gray-200 transition-all duration-300 placeholder:text-gray-400 focus:cursor-text focus:border-primary/50 hover:border-primary/50"
                      />
                      <button
                        type="button"
                        aria-label={showPassword ? '隐藏密码' : '显示密码'}
                        onClick={() => setShowPassword((s) => !s)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    {fieldErrors.password && <p className="text-xs text-red-600 mt-1">{fieldErrors.password}</p>}
                  </div>
                </TabsContent>
              </Tabs>

              {showGlobalError && error && (
                <div className="text-xs text-red-600 font-medium bg-red-50/80 rounded-md">{error}</div>
              )}

              <div className="pt-4">
                <Button
                disabled={loading}
                onClick={handleLogin}
                className="w-full h-11 inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2"
                >
                {loading ? '登录中...' : '登录'}
                </Button>
              </div>
              <div className="text-center mt-6">
                <span className="text-sm text-muted-foreground">首次登录将自动创建账号</span>
              </div>
            </CardContent>
          </Card>
        </div>
        <div className="p-6">
          <p className="text-xs text-muted-foreground text-center">© {currentYear} POD AI 工具平台. All Rights Reserved</p>
        </div>
      </div>

      <LoginContent />
    </div>
  );
};

export default LoginPage;
