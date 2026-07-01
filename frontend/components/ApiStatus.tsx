'use client';
import { useEffect, useState } from 'react';

export default function ApiStatus() {
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://backend-isrohack.onrender.com'}/`, {
          signal: AbortSignal.timeout(65000), // Render free tier can take ~30-60s to wake
        });
        setStatus(res.ok ? 'online' : 'offline');
      } catch {
        setStatus('offline');
      }
    };
    check();
    const interval = setInterval(check, 10000); // Re-check every 10s
    return () => clearInterval(interval);
  }, []);

  const colors = {
    checking: { dot: '#94a3b8', text: 'Connecting...' },
    online:   { dot: '#10b981', text: 'Backend Online' },
    offline:  { dot: '#ef4444', text: 'Backend Offline' },
  };

  const { dot, text } = colors[status];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      fontSize: 11, color: 'var(--text-muted)',
      padding: '6px 10px',
      background: 'rgba(0,0,0,0.3)',
      borderRadius: 20,
      border: '1px solid var(--border)',
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: dot,
        boxShadow: status === 'online' ? `0 0 6px ${dot}` : 'none',
        animation: status === 'online' ? 'pulse-glow 2s ease-in-out infinite' : 'none',
      }} />
      {text}
    </div>
  );
}
