'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import {
  IconMoon, IconRadar, IconCrystal, IconMountain, IconTarget, IconRoute,
  IconDroplet, IconArrowRight, IconCrater, IconRuler, IconScale, IconChart,
  IconTrendUp, IconTarget as IconAim, IconWarning, IconFlask, IconLayers,
  IconShield, IconArrowRight as IconGo,
} from '@/components/Icons';

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
    Icon: IconMoon,
    title: 'Shadow & PSR Mapping',
    desc: 'Illumination modeling, permanently shadowed region identification, and doubly shadowed crater detection.',
    color: '#a855f7',
  },
  {
    href: '/polarimetric',
    Icon: IconRadar,
    title: 'Polarimetric Analysis',
    desc: 'DFSAR Stokes parameters, CPR and DOP computation for ice vs. rock discrimination.',
    color: '#00d4ff',
  },
  {
    href: '/ice-detection',
    Icon: IconCrystal,
    title: 'Ice Detection',
    desc: 'CPR > 1 AND DOP < 0.13 criterion applied within PSRs to identify high-probability ice regions.',
    color: '#60a5fa',
  },
  {
    href: '/terrain',
    Icon: IconMountain,
    title: 'Terrain Analysis',
    desc: 'Slope, roughness, crater morphology and boulder distribution from DEM/OHRC data.',
    color: '#f97316',
  },
  {
    href: '/landing-site',
    Icon: IconTarget,
    title: 'Landing Site Selection',
    desc: 'Multi-criteria evaluation: safety, ice proximity, solar power, and scientific value.',
    color: '#10b981',
  },
  {
    href: '/path-planning',
    Icon: IconRoute,
    title: 'Rover Traverse',
    desc: 'A* optimal path from landing site to target doubly shadowed crater with hazard avoidance.',
    color: '#f472b6',
  },
  {
    href: '/ice-volume',
    Icon: IconDroplet,
    title: 'Ice Volume Estimation',
    desc: 'Dielectric mixing model + Monte Carlo uncertainty quantification for top 5m subsurface ice.',
    color: '#34d399',
  },
];

function StatCard({ Icon, label, value, sub, color }: any) {
  return (
    <div className="stat-card animate-in">
      <div className="stat-icon" style={{ background: `${color}1a` }}>
        <Icon size={18} color={color} />
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
      {/* ─── Hero Section ─────────────────────────────────────── */}
      <section className="hero-section">
        <div className="hero-bg-glow hero-bg-glow--cyan" />
        <div className="hero-bg-glow hero-bg-glow--purple" />

        <div style={{ position: 'relative', zIndex: 2 }}>
          <div className="hero-overline">
            <IconMoon size={13} color="var(--cyan)" />
            ISRO BAH 2026 · Problem Statement 8
          </div>

          <h1 className="hero-title">
            <span className="hero-title-gradient">Lunar Subsurface Ice</span><br />
            Detection &amp; Rover Planning
          </h1>

          <p className="hero-description">
            A comprehensive analysis platform leveraging Chandrayaan-2 Dual Frequency SAR and
            High Resolution Camera data to identify water-ice deposits in doubly shadowed craters
            within Permanently Shadowed Regions of the Lunar South Pole.
          </p>

          <div className="hero-actions">
            <Link href="/ice-detection" className="btn btn-primary">
              View Ice Detection
              <IconArrowRight size={16} color="white" />
            </Link>
            <Link href="/path-planning" className="btn btn-outline">
              Rover Traverse Plan
              <IconArrowRight size={16} />
            </Link>
          </div>

          {/* Quick scientific criterion chips */}
          <div style={{ display: 'flex', gap: 10, marginTop: 28, flexWrap: 'wrap' }}>
            {[
              { label: 'CPR > 1.0', sub: 'Volumetric scattering' },
              { label: 'DOP < 0.13', sub: 'Depolarization' },
              { label: 'T < 110 K', sub: 'Stability gate' },
            ].map(chip => (
              <div key={chip.label} style={{
                display: 'flex', flexDirection: 'column', gap: 2,
                background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '10px 16px',
              }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>{chip.label}</span>
                <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>{chip.sub}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="page-body">
        {/* ─── Key Metrics ─────────────────────────────────────── */}
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <span>Running full analysis pipeline...</span>
          </div>
        ) : error ? (
          <div className="info-block" style={{ borderLeftColor: 'var(--red)' }}>
            <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <IconWarning size={15} color="var(--red)" /> Backend not reachable:
            </strong> {error}
            <br />Start the Python backend: <code style={{ color: 'var(--cyan)' }}>cd backend &amp;&amp; uvicorn app:app --reload</code>
          </div>
        ) : data ? (
          <>
            <h2 className="section-title">Mission Overview</h2>
            <div className="stat-grid">
              <StatCard Icon={IconMoon} label="PSR Regions Identified" value={data.psr_count} sub="Permanently Shadowed" color="#a855f7" />
              <StatCard Icon={IconCrater} label="Doubly Shadowed Craters" value={data.doubly_shadowed_count} sub="Priority ice targets" color="#00d4ff" />
              <StatCard Icon={IconCrystal} label="Ice Regions Detected" value={data.ice_regions_count} sub={`${data.ice_coverage_pct}% area coverage`} color="#60a5fa" />
              <StatCard Icon={IconRuler} label="Total Ice Area" value={`${data.total_ice_area_km2} km²`} sub="Validated CPR+DOP" color="#f97316" />
              <StatCard Icon={IconDroplet} label="Ice Volume Estimate" value={`${(data.total_ice_volume_m3 / 1e6).toFixed(2)} M m³`} sub="Top 5m depth" color="#10b981" />
              <StatCard Icon={IconScale} label="Ice Mass" value={`${data.total_ice_mass_tonnes.toFixed(0)} t`} sub="Monte Carlo median" color="#34d399" />
              <StatCard Icon={IconRadar} label="Mean CPR" value={data.mean_cpr.toFixed(3)} sub="Threshold: >1.0" color="#eab308" />
              <StatCard Icon={IconChart} label="Mean DOP" value={data.mean_dop.toFixed(3)} sub="Threshold: <0.13" color="#f472b6" />
            </div>

            {/* ─── Landing Site & Path Quick View ───────────────── */}
            {data.best_landing_site && (
              <div className="grid-2" style={{ marginBottom: 28 }}>
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">
                      <IconTarget size={16} color="var(--green)" /> Best Landing Site
                    </span>
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
                    <span className="card-title">
                      <IconRoute size={16} color="var(--cyan)" /> Rover Traverse
                    </span>
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
                      View Full Traverse Plan
                      <IconArrowRight size={15} />
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : null}

        {/* ─── Module Cards ─────────────────────────────────────── */}
        <h2 className="section-title">Analysis Modules</h2>
        <div className="grid-3" style={{ gap: 16 }}>
          {MISSION_CARDS.map(card => {
            const CardIcon = card.Icon;
            return (
              <Link key={card.href} href={card.href} className="module-card">
                <div className="module-card-icon" style={{ background: `${card.color}1a`, border: `1px solid ${card.color}33` }}>
                  <CardIcon size={22} color={card.color} />
                </div>
                <h3 style={{ color: card.color }}>{card.title}</h3>
                <p>{card.desc}</p>
                <div className="module-card-link" style={{ color: card.color }}>
                  Explore <IconArrowRight size={14} color={card.color} />
                </div>
              </Link>
            );
          })}
        </div>

        {/* ─── Scientific Framework ─────────────────────────────── */}
        <h2 className="section-title" style={{ marginTop: 32 }}>Scientific Framework</h2>
        <div className="grid-3" style={{ gap: 16 }}>
          {[
            {
              title: 'Ice Detection Criteria',
              Icon: IconCrystal,
              items: ['CPR > 1.0 (Volumetric scattering)', 'DOP < 0.13 (Eliminates rocky surfaces)', 'Located within PSR/doubly shadowed crater', 'Temperature < 110 K stability threshold'],
              color: 'var(--cyan)',
            },
            {
              title: 'Datasets Used',
              Icon: IconLayers,
              items: ['Chandrayaan-2 DFSAR (L-band + S-band)', 'Chandrayaan-2 OHRC (imagery)', 'LOLA Polar DEM (terrain)', 'Solar illumination model (1.5° elevation)'],
              color: 'var(--purple-bright)',
            },
            {
              title: 'Key Outcomes',
              Icon: IconShield,
              items: ['High-probability ice region maps', 'Validated landing site coordinates', 'Optimized rover traverse path', 'Ice volume estimates (top 5m)'],
              color: 'var(--green)',
            }
          ].map(section => {
            const SecIcon = section.Icon;
            return (
              <div key={section.title} className="framework-card">
                <div className="framework-card-title" style={{ color: section.color }}>
                  <SecIcon size={16} color={section.color} />
                  {section.title}
                </div>
                <ul className="framework-list">
                  {section.items.map(item => (
                    <li key={item}>
                      <span className="framework-list-marker" style={{ background: section.color }} />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
