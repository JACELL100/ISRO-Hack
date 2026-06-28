'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

export default function TerrainPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeMap, setActiveMap] = useState<'dem' | 'slope' | 'roughness' | 'ohrc'>('slope');

  useEffect(() => {
    api.terrain().then(setData).finally(() => setLoading(false));
  }, []);

  const maps = data ? {
    dem: { data: data.dem_data, colormap: 'viridis' as const, title: 'Digital Elevation Model (m)' },
    slope: { data: data.slope_data, colormap: 'slope' as const, title: 'Slope (degrees)' },
    roughness: { data: data.roughness_data, colormap: 'plasma' as const, title: 'Surface Roughness (m)' },
    ohrc: { data: data.ohrc_data, colormap: 'shadow' as const, title: 'OHRC Imagery (simulated)' },
  } : {};

  // Crater overlay points
  const craterPoints = data?.craters?.slice(0, 15).map((c: any) => ({
    row: Math.round(c.center_row / 3),
    col: Math.round(c.center_col / 3),
    color: 'rgba(249,115,22,0.9)',
    size: Math.max(3, Math.min(8, c.estimated_radius_pixels / 3)),
  })) || [];

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge">🗺️ Terrain Analysis</div>
        <h1 className="page-title">Terrain Analysis</h1>
        <p className="page-subtitle">
          DEM-based slope, roughness, crater detection · OHRC boulder mapping · Landing safety assessment
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>Safety Criteria:</strong> Landing requires slope {'<'} 15° and surface roughness below threshold.
          Crater morphology analysis detects lobate rims (indicative of ice excavation by impacts).
          Boulder density from OHRC data constrains rover trafficability.
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Analyzing terrain...</span></div>
        ) : data ? (
          <>
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-label">Mean Slope</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--cyan)' }}>{data.slope_stats.mean.toFixed(1)}°</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Max Slope</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--red)' }}>{data.slope_stats.max.toFixed(1)}°</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Safe Area ({'<'}15°)</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--green)' }}>{(data.slope_stats.safe_fraction * 100).toFixed(1)}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Craters Detected</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--orange)' }}>{data.n_craters}</div>
              </div>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="card">
                <div className="card-header">
                  <span className="card-title">🗺️ Terrain Maps</span>
                </div>
                <div className="card-body">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                    {Object.entries(maps).map(([key]) => (
                      <button key={key} className={`btn ${activeMap === key ? 'btn-primary' : 'btn-outline'}`}
                        style={{ padding: '6px 12px', fontSize: 12 }}
                        onClick={() => setActiveMap(key as any)}>
                        {key.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  {maps[activeMap] && (
                    <Heatmap
                      data={maps[activeMap].data}
                      colormap={maps[activeMap].colormap}
                      title={maps[activeMap].title}
                      overlayPoints={activeMap === 'slope' || activeMap === 'dem' ? craterPoints : []}
                    />
                  )}
                  {activeMap === 'slope' && (
                    <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                      🟢 Green: safe ({'<'}5°) · 🟡 Yellow: moderate (5–15°) · 🔴 Red: steep ({'>'} 15°) · Orange dots: craters
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Slope histogram */}
                <div className="card">
                  <div className="card-header"><span className="card-title">📊 Slope Distribution</span></div>
                  <div className="card-body">
                    <div style={{ height: 120, display: 'flex', alignItems: 'flex-end', gap: 1 }}>
                      {data.slope_histogram.map((d: any, i: number) => {
                        const maxC = Math.max(...data.slope_histogram.map((x: any) => x.count));
                        const isSafe = d.bin < 15;
                        return (
                          <div key={i} style={{
                            flex: 1, height: `${(d.count / maxC) * 100}%`,
                            background: isSafe ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)',
                            borderRadius: '2px 2px 0 0', minWidth: 2
                          }} />
                        );
                      })}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                      <span>0°</span><span style={{ color: 'var(--green)' }}>← Safe | Unsafe →</span><span>36°</span>
                    </div>
                  </div>
                </div>

                {/* Terrain stats */}
                <div className="card">
                  <div className="card-header"><span className="card-title">📐 Terrain Statistics</span></div>
                  <div className="card-body">
                    <div className="metric-row"><span className="label">Mean Slope</span><span className="value">{data.slope_stats.mean.toFixed(2)}°</span></div>
                    <div className="metric-row"><span className="label">Max Slope</span><span className="value">{data.slope_stats.max.toFixed(2)}°</span></div>
                    <div className="metric-row"><span className="label">Safe Landing Fraction</span><span className="value" style={{ color: 'var(--green)' }}>{(data.slope_stats.safe_fraction * 100).toFixed(1)}%</span></div>
                    <div className="metric-row"><span className="label">Craters Detected</span><span className="value">{data.n_craters}</span></div>
                    <div className="metric-row"><span className="label">Boulder Coverage</span><span className="value">{data.boulder_coverage_pct?.toFixed(1) ?? '—'}%</span></div>
                  </div>
                </div>

                {/* Crater table */}
                <div className="card">
                  <div className="card-header"><span className="card-title">🕳️ Detected Craters</span></div>
                  <div style={{ padding: '0 16px 16px', overflowX: 'auto' }}>
                    <table className="data-table">
                      <thead>
                        <tr><th>Center</th><th>Radius (px)</th><th>Depth (m)</th></tr>
                      </thead>
                      <tbody>
                        {data.craters.slice(0, 8).map((c: any, i: number) => (
                          <tr key={i}>
                            <td className="mono">{c.center_row},{c.center_col}</td>
                            <td>{c.estimated_radius_pixels}</td>
                            <td className="mono">{c.depth_m?.toFixed(0) ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
