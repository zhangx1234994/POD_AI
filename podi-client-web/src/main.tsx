import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'tdesign-react';
import 'tdesign-react/es/style/index.css';
import './index.css';
import { AuthProvider } from './app/AuthContext';
import AppRouter from './app/router';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ConfigProvider globalConfig={{ classPrefix: 't' }}>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
