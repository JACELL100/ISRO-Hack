'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
import { IconRoute, IconMap, IconTrendUp, IconChart, IconPin, IconWarning, IconShield } from '@/components/Icons';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

function ElevationChart({ profile, slopes }: { profile: number[]; slopes: number[] }) {
  if (!profile?.length) return null;
  const minEl = Math.min(...profile);
  const maxEl = Math.max(...profile);
  const range = maxEl - minEl || 1;
  const pts = profile.map((v, i) => {
    const x = (i / (profile.length - 1)) * 100;
    const y = 100 - ((v - minEl) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={{ width: '100%' }}>
      <svg viewBox="0 0 100 100" style={{ width: '100%', height: 120, display: 'block' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="elev-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cyan)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="var(--cyan)" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <polygon points={`0,100 ${pts} 100,100`} fill="url(#elev-grad)" />
        <polyline points={pts} fill="none" stroke="var(--cyan)" strokeWidth="0.8" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
        <span>Start (Landing)</span>
        <span style={{ color: 'var(--cyan)' }}>Elevation Profile</span>
        <span>Target Crater</span>
      </div>
    </div>
  );
}

export default function PathPlanningPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.pathPlanning().then(setData).finally(() => setLoading(false));
  }, []);

  const metrics = data?.metrics || {};

  // Build overlay for heatmap
  const pathPoints = data?.path_waypoints?.map((p: any) => ({
    row: Math.round(p.row / 3),
    col: Math.round(p.col / 3),
    color: 'rgba(0,212,255,0.8)',
    size: 1,
  })) || [];

  const markerPoints = [
    data?.start && { row: Math.round(data.start.row / 3), col: Math.round(data.start.col / 3), color: '#00ff88', size: 8, label: 'L' },
    data?.goal && { row: Math.round(data.goal.row / 3), col: Math.round(data.goal.col / 3), color: '#ff4444', size: 8, label: 'T' },
  ].filter(Boolean) as any[];

  const allPoints = [...pathPoints, ...markerPoints];
  const pathLine = data?.path_waypoints?.map((p: any) => ({ row: Math.round(p.row / 3), col: Math.round(p.col / 3) })) || [];

  const safetyColor = metrics.path_safety === 'SAFE' ? 'var(--green)' : metrics.path_safety === 'CAUTION' ? 'var(--yellow)' : 'var(--red)';

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge"><IconRoute size={13} /> Rover Traverse</div>
        <h1 className="page-title">Rover Traverse Path Planning</h1>
        <p className="page-subtitle">
          A* optimal path · Terrain-aware cost function · Hazard avoidance · Solar power constraints
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>A* Algorithm:</strong> Cost = 0.35 x slope + 0.20 x roughness + 0.15 x shadow + 0.30 x hazard.
          Slopes {'>'} 25° are impassable. Crater proximity adds hazard penalty.
          Path smoothed with Gaussian filter (sigma=3). Rover speed assumed 100 m/hr.
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Computing optimal traverse...</span></div>
        ) : data?.success === false ? (
          <div className="info-block" style={{ borderLeftColor: 'var(--red)' }}>
            <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <IconWarning size={15} color="var(--red)" /> No traversable path found:
            </strong> {data.error}
          </div>
        ) : data ? (
          <>
            {/* Key metrics */}
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-label">Total Distance</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--cyan)' }}>{metrics.total_distance_km} km</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Max Slope</div>
                <div className="stat-value" style={{ fontSize: 22, color: safetyColor }}>{metrics.max_slope_deg}°</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Est. Time</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--purple-bright)' }}>{metrics.estimated_time_hours} hrs</div>
                <div className="stat-sub">At 100 m/hr</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Energy Est.</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--orange)' }}>{metrics.estimated_energy_kJ} kJ</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Path Safety</div>
                <div className="stat-value" style={{ fontSize: 18, color: safetyColor, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <IconShield size={18} color={safetyColor} /> {metrics.path_safety}
                </div>
              </div>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              {/* Path visualization */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title"><IconMap size={16} /> Traverse Map</span>
                  <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
                    <div className="legend-item"><div className="legend-dot" style={{ background: '#00ff88', width: 8, height: 8 }} />Landing</div>
                    <div className="legend-item"><div className="legend-dot" style={{ background: '#ff4444', width: 8, height: 8 }} />Target</div>
                    <div className="legend-item"><div style={{ width: 16, height: 2, background: 'var(--cyan)', borderRadius: 1 }} />Path</div>
                  </div>
                </div>
                <div className="card-body">
                  {data.cost_map_data && (
                    <Heatmap
                      data={data.cost_map_data}
                      colormap="shadow"
                      title="Cost Map with Planned Traverse"
                      overlayPoints={allPoints}
                      overlayPath={pathLine}
                    />
                  )}

                  {/* Algorithm info */}
                  <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {Object.entries(data.cost_components || {}).map(([key, val]: any) => (
                      <div key={key} style={{
                        background: 'rgba(0,212,255,0.05)', border: '1px solid var(--border)',
                        borderRadius: 8, padding: '6px 12px', fontSize: 11
                      }}>
                        <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                          {key.replace('_weight', '').replace('_', ' ')}:
                        </span>{' '}
                        <span style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>
                          {(val * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Metrics panel */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Elevation profile */}
                <div className="card">
                  <div className="card-header"><span className="card-title"><IconTrendUp size={16} /> Elevation Profile</span></div>
                  <div className="card-body">
                    <ElevationChart profile={metrics.elevation_profile || []} slopes={metrics.slope_profile || []} />
                    <div className="grid-2" style={{ marginTop: 12, gap: 10 }}>
                      <div className="metric-row"><span className="label">Elev. Gain</span><span className="value">+{metrics.elevation_gain_m} m</span></div>
                      <div className="metric-row"><span className="label">Elev. Loss</span><span className="value">-{metrics.elevation_loss_m} m</span></div>
                    </div>
                  </div>
                </div>

                {/* Path metrics */}
                <div className="card">
                  <div className="card-header"><span className="card-title"><IconChart size={16} /> Path Metrics</span></div>
                  <div className="card-body">
                    <div className="metric-row"><span className="label">Distance</span><span className="value">{metrics.total_distance_km} km</span></div>
                    <div className="metric-row"><span className="label">Waypoints</span><span className="value">{metrics.n_waypoints}</span></div>
                    <div className="metric-row"><span className="label">Mean Slope</span><span className="value">{metrics.mean_slope_deg}°</span></div>
                    <div className="metric-row"><span className="label">Max Slope</span><span className="value" style={{ color: safetyColor }}>{metrics.max_slope_deg}°</span></div>
                    <div className="metric-row"><span className="label">Est. Time</span><span className="value">{metrics.estimated_time_hours} hrs</span></div>
                    <div className="metric-row"><span className="label">Energy Est.</span><span className="value">{metrics.estimated_energy_kJ} kJ</span></div>
                    <div className="metric-row"><span className="label">Total Cost</span><span className="value">{metrics.total_cost}</span></div>
                    <div className="metric-row">
                      <span className="label">Safety Rating</span>
                      <span className={`badge ${metrics.path_safety === 'SAFE' ? 'badge-safe' : metrics.path_safety === 'CAUTION' ? 'badge-warn' : 'badge-danger'}`}>
                        {metrics.path_safety}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Start/Goal Info */}
                <div className="card">
                  <div className="card-header"><span className="card-title"><IconPin size={16} /> Route Points</span></div>
                  <div className="card-body">
                    {data.landing_site && (
                      <div style={{ marginBottom: 14, padding: '12px', background: 'rgba(16,185,129,0.07)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--green)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div className="legend-dot" style={{ background: '#00ff88', width: 8, height: 8 }} /> Landing Site
                        </div>
                        <div className="metric-row" style={{ padding: '4px 0' }}><span className="label">Score</span><span className="value">{(data.landing_site.composite_score * 100).toFixed(0)}%</span></div>
                        <div className="metric-row" style={{ padding: '4px 0' }}><span className="label">Elevation</span><span className="value">{data.landing_site.elevation_m} m</span></div>
                        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{data.landing_site.description}</p>
                      </div>
                    )}
                    {data.target_crater && (
                      <div style={{ padding: '12px', background: 'rgba(239,68,68,0.07)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.2)' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--red)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div className="legend-dot" style={{ background: '#ff4444', width: 8, height: 8 }} /> Target: Doubly Shadowed Crater
                        </div>
                        <div className="metric-row" style={{ padding: '4px 0' }}><span className="label">Max Depth</span><span className="value">{data.target_crater.max_depth_m?.toFixed(0)} m</span></div>
                        <div className="metric-row" style={{ padding: '4px 0' }}><span className="label">Area</span><span className="value">{data.target_crater.area_pixels} px</span></div>
                        <div className="metric-row" style={{ padding: '4px 0' }}><span className="label">Min Elevation</span><span className="value">{data.target_crater.min_elevation_m?.toFixed(0)} m</span></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
