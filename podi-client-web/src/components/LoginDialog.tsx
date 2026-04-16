import { useState } from 'react';
import { Button, Dialog, Input, MessagePlugin } from 'tdesign-react';
import { useAuth } from '../app/AuthContext';
import { clientVisualRegistry } from '../config/clientVisuals';

export default function LoginDialog({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { login } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const loginVisual = clientVisualRegistry.loginHero;

  const handleLogin = async () => {
    setLoading(true);
    try {
      await login({ username, password });
      MessagePlugin.success('登录成功，已切换到真实任务与钱包数据。');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : '登录失败';
      MessagePlugin.error(`登录失败：${message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      destroyOnClose
      visible={visible}
      width={760}
      header="登录客户端"
      confirmBtn={
        <Button theme="primary" loading={loading} onClick={handleLogin}>
          登录
        </Button>
      }
      cancelBtn="取消"
      onClose={onClose}
      onConfirm={handleLogin}
    >
      <div className="client-login-dialog">
        <div className="client-login-dialog__visual" style={{ backgroundImage: `url(${loginVisual.url})` }}>
          <span>登录的意义</span>
          <strong>从演示前台切到真实业务前台</strong>
          <p>{loginVisual.help}</p>
          <div className="client-login-dialog__chips">
            <b>未登录：模板、示例素材、本地经营看板</b>
            <b>已登录：真实任务、真实素材、真实钱包数据</b>
          </div>
        </div>
        <div className="client-login-dialog__form">
          <p>请输入已有账号信息。登录不是单纯授权，而是切换数据上下文和商业上下文。</p>
          <label className="client-field">
            <span>用户名</span>
            <Input value={username} onChange={(value) => setUsername(String(value))} placeholder="请输入用户名" />
          </label>
          <label className="client-field">
            <span>密码</span>
            <Input
              type="password"
              value={password}
              onChange={(value) => setPassword(String(value))}
              placeholder="请输入密码"
            />
          </label>
          <div className="client-login-dialog__meta">
            <span>视觉来源：{loginVisual.sourceLabel}</span>
            <span>控制位置：{loginVisual.controlPoint}</span>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
