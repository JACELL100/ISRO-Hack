'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import {
  IconDashboard, IconMoon, IconRadar, IconCrystal, IconMountain,
  IconTarget, IconRoute, IconDroplet, IconMoon as IconLogo,
} from './Icons';

const navItems = [
  { href: '/', label: 'Mission Overview', Icon: IconDashboard, section: 'Dashboard' },
  { href: '/shadow-mapping', label: 'Shadow & PSR Mapping', Icon: IconMoon, section: 'Analysis' },
  { href: '/polarimetric', label: 'Polarimetric Analysis', Icon: IconRadar, section: 'Analysis' },
  { href: '/ice-detection', label: 'Ice Detection', Icon: IconCrystal, section: 'Analysis' },
  { href: '/terrain', label: 'Terrain Analysis', Icon: IconMountain, section: 'Analysis' },
  { href: '/landing-site', label: 'Landing Site', Icon: IconTarget, section: 'Mission Planning' },
  { href: '/path-planning', label: 'Rover Traverse', Icon: IconRoute, section: 'Mission Planning' },
  { href: '/ice-volume', label: 'Ice Volume Estimate', Icon: IconDroplet, section: 'Science' },
];

function ApiStatusBadge() {
  const [status, setStatus] = React.useState<'checking' | 'online' | 'offline'>('checking');

  React.useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(
          `https://backend-isrohack.onrender.com/`,
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
    checking: { color: '#64748b', label: 'Connecting' },
    online:   { color: '#10b981', label: 'API Online' },
    offline:  { color: '#ef4444', label: 'API Offline — start backend' },
  }[status];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '8px 11px', borderRadius: 8,
      background: 'rgba(0,0,0,0.25)',
      border: `1px solid ${status === 'online' ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.05)'}`,
      marginBottom: 12,
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
        <Link href="/" style={{ textDecoration: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 14 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: 'linear-gradient(135deg, rgba(0,212,255,0.18), rgba(168,85,247,0.18))',
              border: '1px solid rgba(0,212,255,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <IconLogo size={20} color="var(--cyan)" />
            </div>
            <div>
              <h1>Lunar Ice Explorer</h1>
              <p>Chandrayaan-2 DFSAR Analysis</p>
            </div>
          </div>
        </Link>
        <div className="sidebar-logo-badge">BAH 2026 · PS-08</div>
      </div>

      <div className="sidebar-nav">
        {sections.map(section => (
          <div key={section}>
            <div className="nav-section-label">{section}</div>
            {navItems.filter(i => i.section === section).map(item => {
              const ItemIcon = item.Icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                >
                  <ItemIcon size={17} className="nav-icon" color={isActive ? 'var(--cyan)' : 'currentColor'} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
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
