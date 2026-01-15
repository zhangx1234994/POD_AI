import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import CryptoJS from 'crypto-js';
import { crossPlatformLogin } from '@/services/userAPI';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

const NativeCrypto = {
  _getDerivedIv(st: string): string {
    const e = "7kp" + st.substring(5, 18);
    const hash = CryptoJS.SHA256(e).toString(CryptoJS.enc.Hex);
    return hash.substring(0, 16).toUpperCase();
  },

  decrypt(hexData: string, keyStr: string, st: string): string | null {
    try {
      const ivStr = this._getDerivedIv(st);
      const key = CryptoJS.enc.Utf8.parse(keyStr);
      const iv = CryptoJS.enc.Utf8.parse(ivStr);

      const encryptedHexStr = CryptoJS.enc.Hex.parse(hexData);
      const encryptedBase64Str = CryptoJS.enc.Base64.stringify(encryptedHexStr);

      const decrypted = CryptoJS.AES.decrypt(
        encryptedBase64Str,
        key,
        {
          iv: iv,
          mode: CryptoJS.mode.CBC,
          padding: CryptoJS.pad.Pkcs7
        }
      );

      const decryptedStr = decrypted.toString(CryptoJS.enc.Utf8);
      return decryptedStr || null;
    } catch (e) {
      console.error("解密失败，可能是密钥或IV不匹配", e);
      return null;
    }
  }
};

const KEY_STR = "8f2d9c4b5a7e1f3d6c8b0a9e7f4d2c1b";
const ST = "k7p2m9v4x8n1q5z3";
const HMAC_SECRET = "your-hmac-secret";

export const SSOHandler: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { checkAuth } = useAuth();
  const [status, setStatus] = useState<'processing' | 'error' | 'success'>('processing');
  const [message, setMessage] = useState('正在进行单点登录...');

  const generateSignature = (params: Record<string, any>): string => {
    const sortedKeys = Object.keys(params).sort();
    const signStr = sortedKeys
      .filter(key => key !== 'signature' && params[key] != null && params[key] !== '')
      .map(key => `${key}=${params[key]}`)
      .join('&');
    
    console.log('Generating Signature for string:', signStr);
    const hash = CryptoJS.HmacSHA256(signStr, HMAC_SECRET);
    return hash.toString(CryptoJS.enc.Hex);
  };

  useEffect(() => {
    const handleSSO = async () => {
      const ticket = searchParams.get('ticket');
      console.log('SSO Received Ticket:', ticket);

      if (!ticket) {
        setStatus('error');
        setMessage('未找到登录凭证');
        return;
      }

      try {
        const decryptedStr = NativeCrypto.decrypt(ticket, KEY_STR, ST);
        console.log('SSO Decrypted Params:', decryptedStr);

        if (!decryptedStr) {
          throw new Error('凭证解密失败');
        }

        // 格式: platform_id|token|account|user_id
        const parts = decryptedStr.split('|');
        console.log('Split parts:', parts); // Debug log

        if (parts.length !== 4) {
          throw new Error(`凭证格式错误: 期望4部分，实际${parts.length}部分`);
        }

        const [platform_id, token, account, user_id] = parts;

        if (!platform_id || platform_id === undefined || platform_id === '') {
          throw new Error('平台不能为空');
        }
        if (!token || token === undefined || token === '') {
          throw new Error('TOKEN不能为空');
        }
        if (!account || account === undefined || account === '') {
          throw new Error('账号不能为空');
        }
        if (!user_id || user_id === undefined || user_id === '') {
          throw new Error('用户主键不能为空');
        }
        const timestamp = Date.now();
        const mobile = account; // 手机号的值使用 account 的值
        // 2. 生成签名
        // 参与签名的参数
        const signParams = {
          platform_id,
          token,
          user_id,
          account,
          mobile,
          timestamp
        };
        const signature = generateSignature(signParams);

        // 3. 调用后端接口
        const res = await crossPlatformLogin({
          platform_id,
          token,
          user_id,
          account,
          mobile,
          timestamp,
          signature
        });

        if (res.data.code === '0' || res.data.code === 200 || (res.status === 200 && res.data.data)) {
            const data = res.data.data || res.data; // 兼容不同结构
            
            // 4. 登录成功
            setStatus('success');
            setMessage('登录成功，正在跳转...');
            
            // 保存 Token 和用户信息
            if (data.token) {
              localStorage.setItem('token', data.token);
              // 如果响应中包含用户ID，保存到localStorage以便请求拦截器使用
              const userId = data.user_id ?? data.userId;
              if (userId) {
                localStorage.setItem('userId', String(userId));
                localStorage.setItem('X-User-Id', String(userId));
                // 保存用户platform到localStorage，用于调试
                localStorage.setItem('platform', String(data.platform));
              }
              // 刷新 AuthContext 状态
              await checkAuth();
            } else {
               throw new Error('登录返回数据缺失Token');
            }
            
            toast.success('单点登录成功');
            
            // 延迟跳转到 Dashboard
            setTimeout(() => {
                navigate('/dashboard', { replace: true });
            }, 1000);
        } else {
            throw new Error(res.data.message || '登录失败');
        }

      } catch (err: any) {
        console.error('SSO Error:', err);
        setStatus('error');
        setMessage(err.message || '单点登录过程中发生错误');
        toast.error(err.message || '登录失败');
      }
    };

    handleSSO();
  }, [searchParams, navigate, checkAuth]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-96 text-center">
        <h2 className="text-2xl font-bold mb-4">AI 平台单点登录</h2>
        
        {status === 'processing' && (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p className="text-gray-600">{message}</p>
          </div>
        )}

        {status === 'error' && (
          <div className="text-red-500">
            <div className="mb-4 text-4xl">❌</div>
            <p>{message}</p>
            <button 
              onClick={() => navigate('/login')}
              className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              返回登录页
            </button>
          </div>
        )}

        {status === 'success' && (
          <div className="text-green-500">
            <div className="mb-4 text-4xl">✅</div>
            <p>{message}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default SSOHandler;
