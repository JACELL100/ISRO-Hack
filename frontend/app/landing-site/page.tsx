'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
import { IconTarget, IconMap, IconPin, IconChart } from '@/components/Icons';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

function ScoreBar({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color }}>{(score * 100).toFixed(0)}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${score * 100}%`, background: color }} />
      </div>
    </div>
  );
}

export default function LandingSitePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSite, setSelectedSite] = useState(0);
  const [activeMap, setActiveMap] = useState<'composite' | 'safety' | 'solar' | 'scientific'>('composite');

  useEffect(() => {
    api.landingSite().then(setData).finally(() => setLoading(false));
  }, []);

  const maps = data ? {
    composite: { data: data.composite_map_data, colormap: 'prob' as const, title: 'Composite Landing Score' },
    safety: { data: data.safety_map_data, colormap: 'slope' as const, title: 'Safety Score (slope + roughness)' },
    solar: { data: data.solar_map_data, colormap: 'viridis' as const, title: 'Solar Power Score' },
    scientific: { data: data.scientific_map_data, colormap: 'plasma' as const, title: 'Scientific Value Score' },
  } : {};

  const site = data?.candidate_sites?.[selectedSite];

  // Overlay candidate sites on map
  const sitePoints = data?.candidate_sites?.map((s: any, i: number) => ({
    row: Math.round(s.row / 3),
    col: Math.round(s.col / 3),
    color: i === 0 ? '#00ff88' : i === selectedSite ? '#00d4ff' : 'rgba(255,255,255,0.5)',
    size: i === 0 ? 8 : 5,
    label: i === 0 ? 'S1' : `${i + 1}`,
  })) || [];

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge"><IconTarget size={13} /> Landing Site</div>
        <h1 className="page-title">Landing Site Selection</h1>
        <p className="page-subtitle">
          Multi-criteria evaluation · Safety · Ice proximity · Solar power · Scientific value
        </p>
      </div>

      <div className="page-body">
        <div className="info-block">
          <strong>Evaluation Criteria:</strong> Composite score = 30% Safety + 25% Ice Proximity + 20% Solar Power + 15% Scientific Value + 10% Trafficability.
          Sites inside PSRs are penalized (no solar power). Minimum safety score of 0.3 required.
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Evaluating landing sites...</span></div>
        ) : data ? (
          <>
            {/* Criteria weights display */}
            <div className="card" style={{ marginBottom: 24, padding: '20px 24px' }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Evaluation Weights:</span>
                {Object.entries(data.criteria_weights).map(([key, weight]: any) => (
                  <div key={key} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: 'rgba(0,212,255,0.07)', borderRadius: 20,
                    padding: '5px 12px', border: '1px solid var(--border)'
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{key.replace('_', ' ')}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>
                      {(weight * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              {/* Map + site selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                  <div className="card-header">
                    <span className="card-title"><IconMap size={16} /> Score Maps</span>
                  </div>
                  <div className="card-body">
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                      {Object.entries(maps).map(([key]) => (
                        <button key={key} className={`btn ${activeMap === key ? 'btn-primary' : 'btn-outline'}`}
                          style={{ padding: '6px 12px', fontSize: 12 }}
                          onClick={() => setActiveMap(key as any)}>
                          {key.charAt(0).toUpperCase() + key.slice(1)}
                        </button>
                      ))}
                    </div>
                    {maps[activeMap] && (
                      <Heatmap
                        data={maps[activeMap].data}
                        colormap={maps[activeMap].colormap}
                        title={maps[activeMap].title}
                        overlayPoints={sitePoints}
                      />
                    )}
                    <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
                      <div className="legend-item"><div className="legend-dot" style={{ background: '#00ff88', width: 10, height: 10 }} />Best site</div>
                      <div className="legend-item"><div className="legend-dot" style={{ background: '#00d4ff', width: 10, height: 10 }} />Selected</div>
                      <div className="legend-item"><div className="legend-dot" style={{ background: 'rgba(255,255,255,0.5)', width: 10, height: 10 }} />Alternatives</div>
                    </div>
                  </div>
                </div>

                {/* Ranked site cards */}
                <div className="card">
                  <div className="card-header"><span className="card-title"><IconPin size={16} /> Candidate Sites</span></div>
                  <div className="card-body" style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {data.candidate_sites?.map((s: any, i: number) => (
                      <div key={i}
                        onClick={() => setSelectedSite(i)}
                        style={{
                          padding: '12px 14px',
                          borderRadius: 10,
                          border: `1px solid ${selectedSite === i ? 'var(--border-hover)' : 'var(--border)'}`,
                          background: selectedSite === i ? 'rgba(0,212,255,0.06)' : 'transparent',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          display: 'flex', alignItems: 'center', gap: 12,
                        }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: '50%',
                          background: i === 0 ? 'linear-gradient(135deg, var(--green), var(--cyan))' : 'rgba(0,212,255,0.12)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 13, fontWeight: 700, color: i === 0 ? 'white' : 'var(--cyan)',
                          flexShrink: 0,
                        }}>
                          {i + 1}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                            Site {i + 1} {i === 0 && <span style={{ color: 'var(--green)', marginLeft: 4 }}>Recommended</span>}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                            Row: {s.row} · Col: {s.col} · Elev: {s.elevation_m}m
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: 15, fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>
                            {(s.composite_score * 100).toFixed(0)}%
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Score</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Selected site detail */}
              {site && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div className="card" style={{ border: '1px solid var(--border-hover)' }}>
                    <div className="card-header">
                      <span className="card-title"><IconTarget size={16} /> Site {selectedSite + 1} — Detail</span>
                      {selectedSite === 0 && <span className="badge badge-safe">Recommended</span>}
                    </div>
                    <div className="card-body">
                      {/* Score rings */}
                      <ScoreBar label="Composite Score" score={site.composite_score} color="var(--cyan)" />
                      <ScoreBar label="Safety (slope + roughness)" score={site.safety_score} color="var(--green)" />
                      <ScoreBar label="Ice Proximity" score={site.ice_proximity_score} color="var(--purple-bright)" />
                      <ScoreBar label="Solar Power" score={site.solar_score} color="var(--yellow)" />
                      <ScoreBar label="Scientific Value" score={site.scientific_score} color="var(--orange)" />
                      <ScoreBar label="Trafficability" score={site.trafficability_score} color="#f472b6" />

                      <div style={{ marginTop: 16, padding: '12px 14px', background: 'rgba(0,0,0,0.25)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Description</div>
                        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{site.description}</p>
                      </div>
                    </div>
                  </div>

                  <div className="card">
                    <div className="card-header"><span className="card-title"><IconChart size={16} /> Evaluation Details</span></div>
                    <div className="card-body">
                      {Object.entries(data.evaluation_criteria).map(([key, desc]: any) => (
                        <div key={key} style={{ padding: '8px 0', borderBottom: '1px solid rgba(0,212,255,0.05)' }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize', marginBottom: 3 }}>
                            {key.replace('_', ' ')}
                          </div>
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{desc}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
