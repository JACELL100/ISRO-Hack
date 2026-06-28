'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';

const navItems = [
  { href: '/', label: 'Mission Overview', icon: '🛰️', section: 'Dashboard' },
  { href: '/shadow-mapping', label: 'Shadow & PSR Mapping', icon: '🌑', section: 'Analysis' },
  { href: '/polarimetric', label: 'Polarimetric Analysis', icon: '📡', section: 'Analysis' },
  { href: '/ice-detection', label: 'Ice Detection', icon: '🧊', section: 'Analysis' },
  { href: '/terrain', label: 'Terrain Analysis', icon: '🗺️', section: 'Analysis' },
  { href: '/landing-site', label: 'Landing Site', icon: '🎯', section: 'Mission Planning' },
  { href: '/path-planning', label: 'Rover Traverse', icon: '🤖', section: 'Mission Planning' },
  { href: '/ice-volume', label: 'Ice Volume Estimate', icon: '💧', section: 'Science' },
];

function ApiStatusBadge() {
  const [status, setStatus] = React.useState<'checking' | 'online' | 'offline'>('checking');

  React.useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/`,
          { signal: AbortSignal.timeout(3000) }
        );
        setStatus(res.ok ? 'online' : 'offline');
      } catch {
        setStatus('offline');
      }
    };
    check();
    const id = setInterval(check, 8000);
    return () => clearInterval(id);
  }, []);

  const cfg = {
    checking: { color: '#64748b', label: 'Connecting...' },
    online:   { color: '#10b981', label: 'API Online' },
    offline:  { color: '#ef4444', label: 'API Offline — start backend' },
  }[status];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '6px 10px', borderRadius: 8,
      background: 'rgba(0,0,0,0.3)',
      border: `1px solid ${status === 'online' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.06)'}`,
      marginBottom: 10,
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: cfg.color,
        boxShadow: status === 'online' ? `0 0 8px ${cfg.color}` : 'none',
        flexShrink: 0,
        animation: status === 'online' ? 'pulse-glow 2s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontSize: 10.5, color: cfg.color, fontWeight: 600, lineHeight: 1.3 }}>
        {cfg.label}
      </span>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const sections = [...new Set(navItems.map(i => i.section))];

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-badge">
          <span>🚀</span> BAH 2026
        </div>
        <h1>Lunar Ice Explorer</h1>
        <p>Chandrayaan-2 DFSAR Analysis</p>
      </div>

      <div className="sidebar-nav">
        {sections.map(section => (
          <div key={section}>
            <div className="nav-section-label">{section}</div>
            {navItems.filter(i => i.section === section).map(item => (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-item ${pathname === item.href ? 'active' : ''}`}
              >
                <span style={{ fontSize: 16 }}>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <ApiStatusBadge />
        <div style={{ marginBottom: 4, color: 'var(--cyan)', fontWeight: 600 }}>PS-08 · Subsurface Ice</div>
        <div>Lunar South Polar Region</div>
        <div style={{ marginTop: 4 }}>Faustini / Shackleton PSR</div>
      </div>
    </nav>
  );
}
