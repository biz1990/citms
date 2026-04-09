import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuthStore } from '../store/useAuthStore';

export interface Notification {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const { user } = useAuthStore();

  useEffect(() => {
    if (!user?.id) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/notifications/ws/${user.id}`;
    
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const notification = JSON.parse(event.data);
        setNotifications(prev => [notification, ...prev]);
        
        // SRS 7.1: Check user preferences before showing toast
        const preferences = user?.preferences;
        if (preferences?.notifications_enabled !== false) {
          toast.info(notification.title, {
            description: notification.message,
          });
        }
      } catch (e) {
        console.error('Failed to parse notification:', e);
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      socket.close();
    };
  }, [user?.id]);

  const markAsRead = (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  };

  return { notifications, markAsRead };
}
