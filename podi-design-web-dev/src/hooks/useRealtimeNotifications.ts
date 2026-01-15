import { useEffect } from 'react';
import { TASK_STATUS_EVENT, WALLET_POINTS_EVENT } from '@/constants/events';

type NotifyPayload = {
  type?: string;
  payload?: any;
};

const WS_PATH = '/api/notify/v1/stream';

export function useRealtimeNotifications(apiBaseUrl?: string) {
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    let socket: WebSocket | null = null;
    let retry = 0;
    let isActive = true;

    const url = buildWsUrl(apiBaseUrl);

    const connect = () => {
      if (!isActive) return;
      try {
        socket = new WebSocket(url);
      } catch (err) {
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        retry = 0;
      };

      socket.onmessage = (event) => {
        try {
          const data: NotifyPayload = JSON.parse(event.data);
          if (data.type === 'task.status') {
            window.dispatchEvent(new CustomEvent(TASK_STATUS_EVENT, { detail: data.payload }));
          } else if (data.type === 'wallet.points') {
            window.dispatchEvent(new CustomEvent(WALLET_POINTS_EVENT, { detail: data.payload }));
          }
        } catch (err) {
          // ignore malformed events
          console.warn('[notify] parse error', err);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (!isActive) return;
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      const timeout = Math.min(30000, 1000 * 2 ** retry);
      retry += 1;
      setTimeout(connect, timeout);
    };

    connect();

    return () => {
      isActive = false;
      socket?.close();
    };
  }, [apiBaseUrl]);
}

function buildWsUrl(baseUrl?: string) {
  const origin = baseUrl ?? window.location.origin;
  if (origin.startsWith('ws')) return `${origin}${WS_PATH}`;
  return origin.replace(/^http/, 'ws') + WS_PATH;
}
