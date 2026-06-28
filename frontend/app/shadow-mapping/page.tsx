'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

export default function ShadowMappingPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeLayer, setActiveLayer] = useState<'dem' | 'shadow' | 'psr' | 'doubly' | 'temp' | 'illum'>('shadow');

  useEffect(() => {
    api.shadowMapping().then(setData).finally(() => setLoading(false));
  }, []);

  const layers = [
    { key: 'dem', label: 'DEM', color: 'viridis' as const },
    { key: 'shadow', label: 'Shadow', color: 'shadow' as const },
    { key: 'psr', label: 'PSR Mask', color: 'plasma' as const },
    { key: 'doubly', label: 'Doubly Shadowed', color: 'ice' as const },
    { key: 'illum', label: 'Illumination', color: 'viridis' as const },
    { key: 'temp', label: 'Temperature', color: 'plasma' as const },
  ];

  const layerData: Record<string, any[][]> = data ? {
    dem: data.dem_data,
    shadow: data.shadow_map_data,
    psr: data.psr_mask_data,
    doubly: data.doubly_shadowed_data,
    illum: data.illumination_data,
    temp: data.temperature_data,
  } : {};

  const activeColormap = layers.find(l => l.key === activeLayer)?.color || 'viridis';

  // Overlay points: doubly shadowed craters
  const overlayPoints = data?.doubly_shadowed_craters?.map((c: any, i: number) => ({
    row: Math.round(c.center_row / 3),
    col: Math.round(c.center_col / 3),
    color: '#00d4ff',
    size: 5,
    label: `DS${i + 1}`,
  })) || [];

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge">🌑 Shadow Mapping</div>
        <h1 className="page-title">Shadow & PSR Mapping</h1>
        <p className="page-subtitle">
          Solar illumination modeling · Permanently Shadowed Region identification · Doubly shadowed crater detection
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>Method:</strong> Ray-casting illumination model at solar elevation 1.5° (typical at lunar south pole).
          PSRs = regions never illuminated from any solar azimuth.
          <strong> Doubly shadowed craters</strong> = small deep depressions within PSRs — coldest environments (~25 K), ideal for ice preservation.
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Computing illumination model...</span></div>
        ) : data ? (
          <>
            {/* Stats Row */}
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-label">PSR Regions</div>
                <div className="stat-value" style={{ fontSize: 24, color: 'var(--purple-bright)' }}>{data.n_psrs}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Shadow Coverage</div>
                <div className="stat-value" style={{ fontSize: 24, color: 'var(--cyan)' }}>{data.shadow_coverage_pct}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">PSR Coverage</div>
                <div className="stat-value" style={{ fontSize: 24, color: 'var(--purple-bright)' }}>{data.psr_coverage_pct}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Doubly Shadowed</div>
                <div className="stat-value" style={{ fontSize: 24, color: 'var(--cyan)' }}>{data.n_doubly_shadowed}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Min Temperature</div>
                <div className="stat-value" style={{ fontSize: 24, color: '#60a5fa' }}>{data.min_temperature_K} K</div>
              </div>
            </div>

            {/* Layer Selector + Heatmap */}
            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="card">
                <div className="card-header">
                  <span className="card-title">🗺️ Data Layer Viewer</span>
                </div>
                <div className="card-body">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                    {layers.map(l => (
                      <button key={l.key} className={`btn ${activeLayer === l.key ? 'btn-primary' : 'btn-outline'}`}
                        style={{ padding: '6px 14px', fontSize: 12 }}
                        onClick={() => setActiveLayer(l.key as any)}>
                        {l.label}
                      </button>
                    ))}
                  </div>
                  {layerData[activeLayer] && (
                    <Heatmap
                      data={layerData[activeLayer]}
                      colormap={activeColormap}
                      title={layers.find(l => l.key === activeLayer)?.label}
                      overlayPoints={activeLayer === 'doubly' || activeLayer === 'shadow' ? overlayPoints : []}
                    />
                  )}
                  <div className="heatmap-legend" style={{ marginTop: 10 }}>
                    <span>Low</span>
                    <div className="legend-bar" style={{
                      background: activeLayer === 'shadow' ? 'linear-gradient(90deg, #050c14, #1e4080)' :
                        activeLayer === 'temp' ? 'linear-gradient(90deg, #0d0887, #cc4778, #f0f921)' :
                          'linear-gradient(90deg, #440154, #208fa0, #5dc962, #fde725)'
                    }} />
                    <span>High</span>
                  </div>
                </div>
              </div>

              {/* PSR Info Panel */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">🌑 PSR Regions</span>
                  </div>
                  <div className="card-body" style={{ padding: '12px 20px' }}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>#</th><th>Area (px)</th><th>Center</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.psr_regions.slice(0, 8).map((r: any) => (
                          <tr key={r.id}>
                            <td className="mono">PSR-{r.id}</td>
                            <td>{r.area_pixels.toLocaleString()}</td>
                            <td className="mono">{r.center_row},{r.center_col}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <span className="card-title">🕳️ Doubly Shadowed Craters</span>
                    <span className="badge badge-tier1">Priority Targets</span>
                  </div>
                  <div className="card-body" style={{ padding: '12px 20px' }}>
                    <table className="data-table">
                      <thead>
                        <tr><th>ID</th><th>Depth (m)</th><th>Area (px)</th><th>Priority</th></tr>
                      </thead>
                      <tbody>
                        {data.doubly_shadowed_craters.map((c: any, i: number) => (
                          <tr key={c.id}>
                            <td className="mono">DS-{i + 1}</td>
                            <td className="mono">{c.max_depth_m.toFixed(0)}</td>
                            <td>{c.area_pixels}</td>
                            <td>
                              <div className="progress-bar" style={{ width: 60 }}>
                                <div className="progress-fill" style={{ width: `${Math.min(100, c.priority_score * 5)}%` }} />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <span className="card-title">🌡️ DEM Statistics</span>
                  </div>
                  <div className="card-body">
                    <div className="metric-row"><span className="label">Min Elevation</span><span className="value">{data.dem_stats.min_m} m</span></div>
                    <div className="metric-row"><span className="label">Max Elevation</span><span className="value">{data.dem_stats.max_m} m</span></div>
                    <div className="metric-row"><span className="label">Mean Elevation</span><span className="value">{data.dem_stats.mean_m} m</span></div>
                    <div className="metric-row"><span className="label">Min Temperature</span><span className="value">{data.min_temperature_K} K</span></div>
                    <div className="metric-row"><span className="label">Mean Temperature</span><span className="value">{data.mean_temperature_K} K</span></div>
                    <div className="metric-row"><span className="label">Sun Elevation</span><span className="value">{data.sun_elevation_deg}°</span></div>
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
