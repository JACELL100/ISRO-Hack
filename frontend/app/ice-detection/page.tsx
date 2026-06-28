'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
import { IconCrystal, IconMap, IconFlask, IconPin } from '@/components/Icons';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

const TIER_COLORS: Record<number, string> = { 1: 'var(--cyan)', 2: 'var(--purple-bright)', 3: 'var(--orange)' };
const TIER_LABELS: Record<number, string> = {
  1: 'Doubly Shadowed (Highest Priority)',
  2: 'High-Confidence PSR Ice',
  3: 'Moderate Confidence',
};

export default function IceDetectionPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeMap, setActiveMap] = useState<'ice' | 'prob' | 'conf'>('prob');

  useEffect(() => {
    api.iceDetection().then(setData).finally(() => setLoading(false));
  }, []);

  const maps = data ? {
    ice: { data: data.ice_mask_data, colormap: 'ice' as const, title: 'Validated Ice Mask (CPR>1 & DOP<0.13)' },
    prob: { data: data.probability_data, colormap: 'prob' as const, title: 'Ice Probability Map [0-1]' },
    conf: { data: data.confidence_data, colormap: 'plasma' as const, title: 'Detection Confidence Map' },
  } : {};

  // Overlay detected ice region centers
  const overlayPoints = data?.ice_regions?.slice(0, 15).map((r: any) => ({
    row: Math.round(r.center_row / 3),
    col: Math.round(r.center_col / 3),
    color: TIER_COLORS[r.priority_tier] || 'white',
    size: r.priority_tier === 1 ? 7 : 5,
    label: r.priority_tier === 1 ? `T${r.id}` : undefined,
  })) || [];

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge"><IconCrystal size={13} /> Ice Detection</div>
        <h1 className="page-title">Subsurface Ice Detection Results</h1>
        <p className="page-subtitle">
          CPR {'>'} 1 AND DOP {'<'} 0.13 within PSRs · Priority-tiered ice regions · Confidence mapping
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>Detection Pipeline:</strong> (1) Apply CPR {'>'} 1 criterion → (2) Apply DOP {'<'} 0.13 filter →
          (3) Restrict to PSR/doubly shadowed regions → (4) Cluster and classify by tier →
          (5) Assign confidence scores weighted by radar strength + shadow context.
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Running ice detection pipeline...</span></div>
        ) : data ? (
          <>
            {/* Summary Stats */}
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-label">Ice Regions</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--cyan)' }}>{data.n_ice_regions}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Tier 1 (Highest)</div>
                <div className="stat-value" style={{ fontSize: 22, color: TIER_COLORS[1] }}>{data.tier1_count}</div>
                <div className="stat-sub">Doubly shadowed</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Tier 2</div>
                <div className="stat-value" style={{ fontSize: 22, color: TIER_COLORS[2] }}>{data.tier2_count}</div>
                <div className="stat-sub">High-confidence PSR</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Total Ice Area</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--green)' }}>{data.total_ice_area_km2} km²</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Ice Coverage</div>
                <div className="stat-value" style={{ fontSize: 22, color: 'var(--orange)' }}>{data.ice_coverage_pct}%</div>
              </div>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="card">
                <div className="card-header">
                  <span className="card-title"><IconMap size={16} /> Detection Maps</span>
                </div>
                <div className="card-body">
                  <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                    {Object.entries(maps).map(([key, val]) => (
                      <button key={key} className={`btn ${activeMap === key ? 'btn-primary' : 'btn-outline'}`}
                        style={{ padding: '6px 14px', fontSize: 12 }}
                        onClick={() => setActiveMap(key as any)}>
                        {key === 'ice' ? 'Ice Mask' : key === 'prob' ? 'Probability' : 'Confidence'}
                      </button>
                    ))}
                  </div>
                  {maps[activeMap] && (
                    <Heatmap
                      data={maps[activeMap].data}
                      colormap={maps[activeMap].colormap}
                      title={maps[activeMap].title}
                      overlayPoints={overlayPoints}
                    />
                  )}
                  {/* Legend */}
                  <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
                    {[1, 2, 3].map(t => (
                      <div key={t} className="legend-item">
                        <div className="legend-dot" style={{ background: TIER_COLORS[t], width: 10, height: 10 }} />
                        <span>Tier {t}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Criteria */}
                <div className="card">
                  <div className="card-header">
                    <span className="card-title"><IconFlask size={16} /> Detection Criteria</span>
                    <span className="badge badge-safe">Applied</span>
                  </div>
                  <div className="card-body">
                    {[
                      { k: 'Method', v: data.detection_criteria.method },
                      { k: 'CPR Threshold', v: `> ${data.detection_criteria.CPR_threshold}` },
                      { k: 'DOP Threshold', v: `< ${data.detection_criteria.DOP_threshold}` },
                    ].map(r => (
                      <div key={r.k} className="metric-row">
                        <span className="label">{r.k}</span>
                        <span className="value" style={{ color: 'var(--text-secondary)', fontFamily: 'inherit', fontSize: 12, textAlign: 'right', maxWidth: 200 }}>{r.v}</span>
                      </div>
                    ))}
                    <div style={{ marginTop: 12 }}>
                      {[1, 2, 3].map(t => (
                        <div key={t} style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,212,255,0.05)' }}>
                          <span className={`badge badge-tier${t}`} style={{ marginBottom: 4, display: 'inline-flex' }}>Tier {t}</span>
                          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                            {data.priority_summary[`tier${t}`]}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Ice regions table */}
                <div className="card">
                  <div className="card-header">
                    <span className="card-title"><IconPin size={16} /> Detected Ice Regions</span>
                  </div>
                  <div style={{ overflowX: 'auto', padding: '0 16px 16px' }}>
                    <table className="data-table">
                      <thead>
                        <tr><th>ID</th><th>Tier</th><th>Area km²</th><th>Confidence</th></tr>
                      </thead>
                      <tbody>
                        {data.ice_regions.slice(0, 12).map((r: any) => (
                          <tr key={r.id}>
                            <td className="mono">R-{r.id}</td>
                            <td><span className={`badge badge-tier${r.priority_tier}`} style={{ fontSize: 10 }}>T{r.priority_tier}</span></td>
                            <td className="mono">{r.area_km2}</td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <div className="progress-bar" style={{ width: 60 }}>
                                  <div className="progress-fill" style={{ width: `${r.mean_confidence * 100}%` }} />
                                </div>
                                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{(r.mean_confidence * 100).toFixed(0)}%</span>
                              </div>
                            </td>
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
