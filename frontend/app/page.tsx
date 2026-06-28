'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Overview {
  scene_metadata: any;
  psr_count: number;
  doubly_shadowed_count: number;
  ice_regions_count: number;
  ice_coverage_pct: number;
  total_ice_area_km2: number;
  total_ice_volume_m3: number;
  total_ice_mass_tonnes: number;
  best_landing_site: any;
  rover_path_distance_km: number | null;
  rover_path_safety: string | null;
  mean_cpr: number;
  mean_dop: number;
}

const MISSION_CARDS = [
  {
    href: '/shadow-mapping',
    icon: '🌑',
    title: 'Shadow & PSR Mapping',
    desc: 'Illumination modeling, permanently shadowed region identification, and doubly shadowed crater detection.',
    color: 'var(--purple)',
  },
  {
    href: '/polarimetric',
    icon: '📡',
    title: 'Polarimetric Analysis',
    desc: 'DFSAR Stokes parameters, CPR and DOP computation for ice vs. rock discrimination.',
    color: 'var(--cyan)',
  },
  {
    href: '/ice-detection',
    icon: '🧊',
    title: 'Ice Detection',
    desc: 'CPR > 1 AND DOP < 0.13 criterion applied within PSRs to identify high-probability ice regions.',
    color: '#60a5fa',
  },
  {
    href: '/terrain',
    icon: '🗺️',
    title: 'Terrain Analysis',
    desc: 'Slope, roughness, crater morphology and boulder distribution from DEM/OHRC data.',
    color: 'var(--orange)',
  },
  {
    href: '/landing-site',
    icon: '🎯',
    title: 'Landing Site Selection',
    desc: 'Multi-criteria evaluation: safety, ice proximity, solar power, and scientific value.',
    color: 'var(--green)',
  },
  {
    href: '/path-planning',
    icon: '🤖',
    title: 'Rover Traverse',
    desc: 'A* optimal path from landing site to target doubly shadowed crater with hazard avoidance.',
    color: '#f472b6',
  },
  {
    href: '/ice-volume',
    icon: '💧',
    title: 'Ice Volume Estimation',
    desc: 'Dielectric mixing model + Monte Carlo uncertainty quantification for top 5m subsurface ice.',
    color: '#34d399',
  },
];

function StatCard({ icon, label, value, sub, color }: any) {
  return (
    <div className="stat-card animate-in">
      <div className={`stat-icon`} style={{ background: `${color}22` }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export default function HomePage() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.overview()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge">🛰️ ISRO BAH 2026 · Problem Statement 8</div>
        <h1 className="page-title">Lunar Subsurface Ice Detection & Rover Planning</h1>
        <p className="page-subtitle">
          Chandrayaan-2 DFSAR/OHRC based analysis of the Lunar South Polar Region
          · Faustini Permanently Shadowed Region
        </p>
      </div>

      <div className="page-body">
        {/* Hero Banner */}
        <div className="card" style={{
          marginBottom: 28,
          background: 'linear-gradient(135deg, rgba(0,20,50,0.95) 0%, rgba(30,10,60,0.95) 100%)',
          border: '1px solid rgba(0,212,255,0.3)',
          padding: '32px 36px',
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -40, right: -40,
            width: 300, height: 300,
            background: 'radial-gradient(ellipse, rgba(0,212,255,0.08) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />
          <div style={{
            position: 'absolute', bottom: -60, left: '50%',
            width: 400, height: 200,
            background: 'radial-gradient(ellipse, rgba(168,85,247,0.06) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <div style={{ fontSize: 72, lineHeight: 1 }} className="animate-glow">🌕</div>
            <div>
              <h2 style={{
                fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800,
                color: 'var(--text-primary)', marginBottom: 8
              }}>
                Detection & Characterization of Subsurface Ice
              </h2>
              <p style={{ color: 'var(--text-secondary)', maxWidth: 680, lineHeight: 1.7, fontSize: 14 }}>
                Using Chandrayaan-2 Dual Frequency SAR and High Resolution Camera data to identify
                water-ice deposits in <strong style={{ color: 'var(--cyan)' }}>doubly shadowed craters</strong> within
                Permanently Shadowed Regions (PSRs). Combined CPR {'>'} 1 AND DOP {'<'} 0.13 criterion
                applied for unambiguous ice detection.
              </p>
              <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                <Link href="/ice-detection" className="btn btn-primary">
                  🧊 View Ice Detection Results
                </Link>
                <Link href="/path-planning" className="btn btn-outline">
                  🤖 Rover Traverse Plan
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <span>Running full analysis pipeline...</span>
          </div>
        ) : error ? (
          <div className="info-block" style={{ borderLeftColor: 'var(--red)' }}>
            <strong>⚠️ Backend not reachable:</strong> {error}
            <br />Start the Python backend: <code style={{ color: 'var(--cyan)' }}>cd backend && uvicorn app:app --reload</code>
          </div>
        ) : data ? (
          <>
            <div className="stat-grid">
              <StatCard icon="🌑" label="PSR Regions Identified" value={data.psr_count} sub="Permanently Shadowed" color="var(--purple-bright)" />
              <StatCard icon="🕳️" label="Doubly Shadowed Craters" value={data.doubly_shadowed_count} sub="Priority ice targets" color="var(--cyan)" />
              <StatCard icon="🧊" label="Ice Regions Detected" value={data.ice_regions_count} sub={`${data.ice_coverage_pct}% area coverage`} color="#60a5fa" />
              <StatCard icon="📐" label="Total Ice Area" value={`${data.total_ice_area_km2} km²`} sub="Validated CPR+DOP" color="var(--orange)" />
              <StatCard icon="💧" label="Ice Volume Estimate" value={`${(data.total_ice_volume_m3 / 1e6).toFixed(2)} M m³`} sub="Top 5m depth" color="var(--green)" />
              <StatCard icon="⚖️" label="Ice Mass" value={`${data.total_ice_mass_tonnes.toFixed(0)} t`} sub="Monte Carlo median" color="#34d399" />
              <StatCard icon="📡" label="Mean CPR" value={data.mean_cpr.toFixed(3)} sub="Threshold: >1.0" color="var(--yellow)" />
              <StatCard icon="📊" label="Mean DOP" value={data.mean_dop.toFixed(3)} sub="Threshold: <0.13" color="#f472b6" />
            </div>

            {/* Landing Site & Path Quick View */}
            {data.best_landing_site && (
              <div className="grid-2" style={{ marginBottom: 28 }}>
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">🎯 Best Landing Site</span>
                    <span className="badge badge-safe">Recommended</span>
                  </div>
                  <div className="card-body">
                    <div className="metric-row">
                      <span className="label">Composite Score</span>
                      <span className="value">{(data.best_landing_site.composite_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Safety Score</span>
                      <span className="value">{(data.best_landing_site.safety_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Solar Power Score</span>
                      <span className="value">{(data.best_landing_site.solar_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Elevation</span>
                      <span className="value">{data.best_landing_site.elevation_m} m</span>
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${data.best_landing_site.composite_score * 100}%` }} />
                      </div>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 10 }}>
                      {data.best_landing_site.description}
                    </p>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <span className="card-title">🤖 Rover Traverse</span>
                    <span className={`badge ${data.rover_path_safety === 'SAFE' ? 'badge-safe' : data.rover_path_safety === 'CAUTION' ? 'badge-warn' : 'badge-danger'}`}>
                      {data.rover_path_safety || 'Pending'}
                    </span>
                  </div>
                  <div className="card-body">
                    <div className="metric-row">
                      <span className="label">Path Distance</span>
                      <span className="value">{data.rover_path_distance_km?.toFixed(3) ?? '—'} km</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Algorithm</span>
                      <span className="value" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>A* Terrain-Aware</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Objective</span>
                      <span className="value" style={{ color: 'var(--text-secondary)', fontFamily: 'inherit', fontSize: 12 }}>Doubly Shadowed Crater</span>
                    </div>
                    <Link href="/path-planning" className="btn btn-outline" style={{ marginTop: 16, width: '100%', justifyContent: 'center' }}>
                      View Full Traverse Plan →
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : null}

        {/* Module Cards */}
        <h2 className="section-title">Analysis Modules</h2>
        <div className="grid-3" style={{ gap: 16 }}>
          {MISSION_CARDS.map(card => (
            <Link key={card.href} href={card.href} style={{ textDecoration: 'none' }}>
              <div className="card" style={{ padding: '22px 24px', cursor: 'pointer', height: '100%' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>{card.icon}</div>
                <h3 style={{
                  fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 700,
                  color: card.color, marginBottom: 8
                }}>{card.title}</h3>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{card.desc}</p>
                <div style={{ marginTop: 16, color: card.color, fontSize: 12, fontWeight: 600 }}>
                  Explore →
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Scientific Framework */}
        <div className="card" style={{ marginTop: 28, padding: '24px 28px' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)' }}>
            🔬 Scientific Framework
          </h2>
          <div className="grid-3" style={{ gap: 16 }}>
            {[
              {
                title: 'Ice Detection Criteria',
                items: ['CPR > 1.0 (Volumetric scattering)', 'DOP < 0.13 (Eliminates rocky surfaces)', 'Located within PSR/doubly shadowed crater', 'Temperature < 110 K stability threshold'],
                color: 'var(--cyan)',
              },
              {
                title: 'Datasets Used',
                items: ['Chandrayaan-2 DFSAR (L-band + S-band)', 'Chandrayaan-2 OHRC (imagery)', 'LOLA Polar DEM (terrain)', 'Solar illumination model (1.5° elevation)'],
                color: 'var(--purple-bright)',
              },
              {
                title: 'Key Outcomes',
                items: ['High-probability ice region maps', 'Validated landing site coordinates', 'Optimized rover traverse path', 'Ice volume estimates (top 5m)'],
                color: 'var(--green)',
              }
            ].map(section => (
              <div key={section.title} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: '16px 18px', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: section.color, marginBottom: 10 }}>{section.title}</div>
                <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {section.items.map(item => (
                    <li key={item} style={{ fontSize: 12.5, color: 'var(--text-secondary)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <span style={{ color: section.color, marginTop: 2 }}>▸</span> {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
