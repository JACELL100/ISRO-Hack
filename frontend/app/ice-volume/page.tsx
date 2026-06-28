'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

function MonteCarloBars({ samples, color = 'var(--cyan)' }: { samples: number[]; color?: string }) {
  if (!samples?.length) return null;
  const bins = 20;
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const range = max - min || 1;
  const counts = new Array(bins).fill(0);
  samples.forEach(v => {
    const i = Math.min(bins - 1, Math.floor(((v - min) / range) * bins));
    counts[i]++;
  });
  const maxCount = Math.max(...counts);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 80 }}>
      {counts.map((c, i) => (
        <div key={i} style={{
          flex: 1, height: `${(c / maxCount) * 100}%`,
          background: color, opacity: 0.75,
          borderRadius: '2px 2px 0 0', minWidth: 2,
          transition: 'height 0.5s ease',
        }} />
      ))}
    </div>
  );
}

export default function IceVolumePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.iceVolume().then(setData).finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge">💧 Ice Volume</div>
        <h1 className="page-title">Subsurface Ice Volume Estimation</h1>
        <p className="page-subtitle">
          CRIM dielectric mixing model · CPR inversion · Monte Carlo uncertainty (n=2000)
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>Model:</strong> ε_eff = [f·√ε_ice + (1-f)·√ε_regolith]² (CRIM mixing model).
          Ice fraction <em>f</em> inverted from CPR values. Ice volume = f × area × depth (5m).
          Monte Carlo (2000 samples) propagates uncertainty in ice fraction and depth.
          ε_ice = 3.15, ε_regolith = 3.0 (typical lunar values).
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Running Monte Carlo estimation...</span></div>
        ) : data ? (
          <>
            {/* Hero totals */}
            <div className="card" style={{
              marginBottom: 24, padding: '28px 32px',
              background: 'linear-gradient(135deg, rgba(0,20,50,0.95), rgba(20,5,50,0.95))',
              border: '1px solid rgba(0,212,255,0.25)',
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16, fontWeight: 600 }}>
                TOTAL SUBSURFACE ICE ESTIMATE (Top {data.depth_modeled_m}m)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
                {[
                  { label: 'Ice Area', value: `${data.total_ice_area_km2} km²`, color: 'var(--cyan)' },
                  { label: 'Ice Volume (P50)', value: `${(data.total_volume_m3 / 1e6).toFixed(3)} M m³`, color: 'var(--purple-bright)' },
                  { label: 'Ice Mass', value: `${data.total_mass_tonnes.toFixed(0)} t`, color: 'var(--green)' },
                  { label: 'Mean Ice Fraction', value: `${data.mean_ice_fraction_pct}%`, color: 'var(--orange)' },
                ].map(item => (
                  <div key={item.label} style={{ textAlign: 'center' }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 800, color: item.color }}>{item.value}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{item.label}</div>
                  </div>
                ))}
              </div>
              {/* Uncertainty band */}
              <div style={{ marginTop: 20, padding: '12px 16px', background: 'rgba(0,0,0,0.3)', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Volume Uncertainty (90% CI)</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    P5: {(data.volume_p5_m3 / 1e6).toFixed(3)} M m³
                  </span>
                  <div style={{ flex: 1, height: 6, background: 'rgba(0,212,255,0.1)', borderRadius: 3, position: 'relative' }}>
                    <div style={{
                      position: 'absolute',
                      left: `${(data.volume_p5_m3 / data.volume_p95_m3) * 100}%`,
                      right: '0%',
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--cyan), var(--purple-bright))',
                      borderRadius: 3,
                    }} />
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    P95: {(data.volume_p95_m3 / 1e6).toFixed(3)} M m³
                  </span>
                </div>
              </div>
            </div>

            <div className="grid-2" style={{ alignItems: 'start', marginBottom: 24 }}>
              {/* Monte Carlo distributions */}
              <div className="card">
                <div className="card-header"><span className="card-title">📊 Monte Carlo Distributions</span></div>
                <div className="card-body">
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>Ice Fraction Samples</div>
                    <MonteCarloBars samples={data.ice_fraction_histogram} color="rgba(0,212,255,0.7)" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                      <span>Low fraction</span><span>High fraction</span>
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>Volume Samples (m³)</div>
                    <MonteCarloBars samples={data.volume_histogram} color="rgba(168,85,247,0.7)" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                      <span>Min</span><span>Volume estimate</span><span>Max</span>
                    </div>
                  </div>
                  <div style={{ marginTop: 16 }}>
                    <div className="metric-row"><span className="label">Model</span><span className="value" style={{ color: 'var(--text-secondary)', fontFamily: 'inherit', fontSize: 11 }}>{data.model_description}</span></div>
                    <div className="metric-row"><span className="label">MC Samples</span><span className="value">2000</span></div>
                    <div className="metric-row"><span className="label">Depth Modeled</span><span className="value">{data.depth_modeled_m} m</span></div>
                  </div>
                </div>
              </div>

              {/* Physical constants & CPR table */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                  <div className="card-header"><span className="card-title">⚛️ Physical Parameters</span></div>
                  <div className="card-body">
                    {Object.entries(data.physical_constants || {}).map(([key, val]: any) => (
                      <div key={key} className="metric-row">
                        <span className="label">{key.replace(/_/g, ' ')}</span>
                        <span className="value">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div className="card-header"><span className="card-title">📈 CPR → Ice Fraction Lookup</span></div>
                  <div style={{ padding: '0 16px 16px', overflowX: 'auto' }}>
                    <table className="data-table">
                      <thead>
                        <tr><th>CPR</th><th>Ice %</th><th>Uncertainty</th></tr>
                      </thead>
                      <tbody>
                        {data.cpr_to_ice_table?.slice(0, 10).map((row: any) => (
                          <tr key={row.cpr}>
                            <td className="mono">{row.cpr}</td>
                            <td className="mono" style={{ color: 'var(--cyan)' }}>{row.ice_fraction_pct}%</td>
                            <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>±{row.uncertainty_pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            {/* Region breakdown */}
            <div className="card">
              <div className="card-header">
                <span className="card-title">🧊 Volume by Ice Region</span>
                <span className="badge badge-tier1">{data.regions?.length} Regions</span>
              </div>
              <div style={{ overflowX: 'auto', padding: '0 16px 16px' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Region</th><th>Tier</th><th>Area km²</th><th>CPR</th>
                      <th>Ice %</th><th>Vol P50 (m³)</th><th>Vol Range</th><th>Mass (t)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.regions?.map((r: any) => (
                      <tr key={r.region_id}>
                        <td className="mono">R-{r.region_id}</td>
                        <td><span className={`badge badge-tier${r.priority_tier}`} style={{ fontSize: 9 }}>T{r.priority_tier}</span></td>
                        <td className="mono">{r.area_km2}</td>
                        <td className="mono" style={{ color: r.mean_cpr > 1 ? 'var(--green)' : 'var(--text-muted)' }}>{r.mean_cpr}</td>
                        <td className="mono" style={{ color: 'var(--cyan)' }}>{r.ice_fraction_pct}%</td>
                        <td className="mono">{r.volume_m3_p50?.toFixed(0)}</td>
                        <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          [{r.volume_m3_p5?.toFixed(0)} – {r.volume_m3_p95?.toFixed(0)}]
                        </td>
                        <td className="mono">{r.mass_tonnes?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
