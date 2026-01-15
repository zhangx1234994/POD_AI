import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { authAPI } from '@/utils/http';
import { useAuth } from '@/contexts/AuthContext';
import { Eye, EyeOff } from 'lucide-react';
import { LoginContent } from '../Login/LoginContent';

export function RegisterPage({
  onSuccess,
  onSwitchLogin,
}: {
  onSuccess?: () => void;
  onSwitchLogin?: () => void;
}) {
  const [mode, setMode] = useState<'phone' | 'username'>('phone');
  const [phone, setPhone] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const currentYear = new Date().getFullYear();

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (mode === 'phone') {
      if (!phone.trim()) {
        errors.phone = '手机号不能为空';
      } else if (!/^\d{6,15}$/.test(phone.replace(/\s+/g, ''))) {
        errors.phone = '手机号格式不正确';
      }
    } else {
      if (!username.trim()) {
        errors.username = '用户名不能为空';
      } else if (username.length < 6) {
        errors.username = '用户名长度不能小于6个字符';
      }
    }

    if (!password.trim()) {
      errors.password = '密码不能为空';
    } else if (password.length < 6) {
      errors.password = '密码长度不能小于6个字符';
    }

    if (confirmPassword !== password) {
      errors.confirmPassword = '两次输入的密码不一致';
    }

    if (!verifyCode.trim()) {
      errors.verifyCode = '请输入验证码';
    }

    if (!accepted) {
      errors.accepted = '请阅读并同意服务条款';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSendCode = async () => {
    // placeholder: there's no dedicated API in authAPI for sending SMS in this project.
    // For now just simulate
    alert('验证码已发送（模拟）');
  };

  const handleRegister = async () => {
    if (!validateForm()) return;

    setLoading(true);
    setError(null);
    try {
      // Map form values to existing register API: use username field when available,
      // otherwise use phone as username placeholder; email omitted in this UI.
      const finalUsername = mode === 'username' ? username : phone;
      const data = await authAPI.register(finalUsername, '', password);
      if (!data) throw new Error('注册响应数据为空');

      // 自动登录（用 finalUsername）
      await login(finalUsername, password);
      if (typeof onSuccess === 'function') onSuccess();
    } catch (e: any) {
      const userFriendlyMessage = e?.friendlyMessage || e?.response?.data?.message || e?.message || '注册失败';
      setError(userFriendlyMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white dark:bg-gray-950">
      {/* Left: form */}
      <div className="w-full lg:w-1/2 flex flex-col">    
        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <Card className="shadow-2xl bg-white border-0 w-full max-w-md">
            <CardHeader className="space-y-2 pb-2 px-0 pt-0">
              <CardTitle className="text-3xl font-semibold flex items-center gap-2">
                <span className="inline-block text-4xl">👋</span>欢迎
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 px-0 [&:last-child]:pb-0">
              <div className="flex items-center gap-2 bg-gray-100 rounded-full p-1">
                <button
                  onClick={() => setMode('phone')}
                  className={`flex-1 py-2 rounded-full text-sm ${mode === 'phone' ? 'bg-white shadow' : ''}`}
                >
                  手机号注册
                </button>
                <button
                  onClick={() => setMode('username')}
                  className={`flex-1 py-2 rounded-full text-sm ${mode === 'username' ? 'bg-white shadow' : ''}`}
                >
                  用户名注册
                </button>
              </div>

              {mode === 'phone' ? (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">手机号</label>
                  <Input
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value);
                      if (fieldErrors.phone) setFieldErrors((prev) => ({ ...prev, phone: '' }));
                    }}
                    placeholder="请输入手机号"
                    className={`bg-white border ${fieldErrors.phone ? 'border-red-300' : 'border-gray-200'}`}
                  />
                  {fieldErrors.phone && <p className="text-xs text-red-600">{fieldErrors.phone}</p>}
                </div>
              ) : (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">用户名</label>
                  <Input
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      if (fieldErrors.username) setFieldErrors((prev) => ({ ...prev, username: '' }));
                    }}
                    placeholder="请输入用户名"
                    className={`bg-white border ${fieldErrors.username ? 'border-red-300' : 'border-gray-200'}`}
                  />
                  {fieldErrors.username && <p className="text-xs text-red-600">{fieldErrors.username}</p>}
                </div>
              )}

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">密码</label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: '' }));
                    }}
                    placeholder="请输入密码"
                    className={`bg-white border ${fieldErrors.password ? 'border-red-300' : 'border-gray-200'} pr-10`}
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
                {fieldErrors.password && <p className="text-xs text-red-600">{fieldErrors.password}</p>}
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">确认密码</label>
                <div className="relative">
                  <Input
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (fieldErrors.confirmPassword) setFieldErrors((prev) => ({ ...prev, confirmPassword: '' }));
                    }}
                    placeholder="请输入确认密码"
                    className={`bg-white border ${fieldErrors.confirmPassword ? 'border-red-300' : 'border-gray-200'} pr-10`}
                  />
                  <button
                    type="button"
                    aria-label={showConfirm ? '隐藏确认密码' : '显示确认密码'}
                    onClick={() => setShowConfirm((s) => !s)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                {fieldErrors.confirmPassword && <p className="text-xs text-red-600">{fieldErrors.confirmPassword}</p>}
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm leading-none font-medium select-none">验证码</label>
                <div className="flex items-center gap-2">
                  <Input
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    placeholder="请输入验证码"
                    className={`flex-1 bg-white border ${fieldErrors.verifyCode ? 'border-red-300' : 'border-gray-200'}`}
                  />
                  <Button onClick={handleSendCode} className="whitespace-nowrap">发送验证码</Button>
                </div>
                {fieldErrors.verifyCode && <p className="text-xs text-red-600">{fieldErrors.verifyCode}</p>}
              </div>

              <div className="flex items-center gap-2">
                <input type="checkbox" id="accept" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
                <label htmlFor="accept" className="text-xs">
                  我已阅读并同意&nbsp;
                  <a href="/terms" className="text-blue-600 hover:underline">服务条款</a>
                  &nbsp;和&nbsp;
                  <a href="/privacy" className="text-blue-600 hover:underline">隐私政策</a>
                </label>
              </div>
              {fieldErrors.accepted && <p className="text-xs text-red-600">{fieldErrors.accepted}</p>}

              {error && (
                <div className="text-sm text-red-600 font-medium bg-red-50/80 px-3 py-2 rounded-md border border-red-100">{error}</div>
              )}

              <div className="pt-2">
                <Button
                  disabled={loading}
                  onClick={handleRegister}
                  className="w-full h-11 inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2"
                >
                  {loading ? '注册中...' : '注册'}
                </Button>
                <div className="text-center mt-4">
                  <span className="text-sm text-gray-600">已有账号? </span>
                  <button onClick={() => onSwitchLogin && onSwitchLogin()} className="text-blue-600 hover:underline text-sm font-medium">立即登录</button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        <div className="p-6">
          <p className="text-xs text-muted-foreground text-center">© {currentYear} POD AI 工具平台. All Rights Reserved</p>
        </div>
      </div>

      {/* Right: form */}
      <LoginContent />
    </div>
  );
};

export default RegisterPage;
