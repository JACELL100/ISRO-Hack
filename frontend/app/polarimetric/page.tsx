'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
const Heatmap = dynamic(() => import('@/components/Heatmap'), { ssr: false });

function BarChart({ data, color = 'var(--cyan)', threshold }: { data: { bin: number; count: number }[]; color?: string; threshold?: number }) {
  if (!data?.length) return null;
  const maxCount = Math.max(...data.map(d => d.count));
  return (
    <div style={{ width: '100%', height: 140, display: 'flex', alignItems: 'flex-end', gap: 1, paddingTop: 8, position: 'relative' }}>
      {threshold !== undefined && (
        <div style={{ position: 'absolute', left: `${(threshold / (data[data.length - 1].bin || 1)) * 100}%`, top: 0, bottom: 0, width: 2, background: 'var(--red)', opacity: 0.8, zIndex: 2 }}>
          <div style={{ position: 'absolute', top: 4, left: 4, fontSize: 9, color: 'var(--red)', whiteSpace: 'nowrap' }}>T: {threshold}</div>
        </div>
      )}
      {data.map((d, i) => (
        <div key={i} style={{
          flex: 1, height: `${(d.count / maxCount) * 100}%`,
          background: threshold !== undefined ? (d.bin > threshold ? 'rgba(239,68,68,0.7)' : color) : color,
          opacity: 0.8, borderRadius: '2px 2px 0 0', minWidth: 2,
        }} />
      ))}
    </div>
  );
}

function BandBadge({ label, freq, wl, depth, color }: { label: string; freq: string; wl: string; depth: string; color: string }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, background: `${color}15`, border: `1px solid ${color}40`, borderRadius: 8, padding: '8px 14px' }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color }}>{label}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{freq} · λ={wl} · depth≈{depth}</div>
      </div>
    </div>
  );
}

export default function PolarimetricPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'lband' | 'sband' | 'dual'>('lband');
  const [activeMap, setActiveMap] = useState<string>('cpr');

  useEffect(() => {
    api.polarimetric().then(d => { setData(d); }).finally(() => setLoading(false));
  }, []);

  const lbandMaps: Record<string, { data: any[][]; colormap: any; label: string; hint: string }> = data ? {
    cpr:     { data: data.cpr_data,     colormap: 'cpr',     label: 'L-band CPR (430 MHz, 24 cm)',  hint: '🔴 Red: CPR > 1 — volumetric scattering (ice). Blue: surface.' },
    dop:     { data: data.dop_data,     colormap: 'dop',     label: 'L-band DOP',                   hint: '🔵 Blue: DOP < 0.13 — depolarized = ice candidate.' },
    s0:      { data: data.s0_data,      colormap: 'viridis', label: 'L-band Total Power (S₀)',       hint: 'Total backscatter power from L-band DFSAR.' },
    entropy: { data: data.entropy_data, colormap: 'plasma',  label: 'L-band Scattering Entropy',     hint: 'Higher entropy → more random scattering (ice-like).' },
  } : {};

  const sbandMaps: Record<string, { data: any[][]; colormap: any; label: string; hint: string }> = data ? {
    cpr_s: { data: data.cpr_s_data, colormap: 'cpr',     label: 'S-band CPR (2.5 GHz, 9 cm)', hint: '🔴 Red: CPR_S > 1 — S-band volumetric scattering.' },
    dop_s: { data: data.dop_s_data, colormap: 'dop',     label: 'S-band DOP',                  hint: '🔵 Blue: DOP_S < 0.13 — S-band depolarization.' },
    s0_s:  { data: data.s0_s_data,  colormap: 'viridis', label: 'S-band Total Power (S₀)',      hint: 'Total backscatter power from S-band DFSAR.' },
  } : {};

  const dualMaps: Record<string, { data: any[][]; colormap: any; label: string; hint: string }> = data ? {
    dfr:            { data: data.dfr_data,                colormap: 'viridis', label: 'Dual-Frequency Ratio (CPR_L / CPR_S)',  hint: 'DFR > 1 → deep subsurface ice. DFR ≈ 1 → surface roughness.' },
    dual_conf:      { data: data.dual_confidence_data,    colormap: 'plasma',  label: 'Dual-Frequency Ice Confidence',          hint: 'Combined L+S confidence. High = both bands agree on ice.' },
    dual_confirmed: { data: data.ice_dual_confirmed_data, colormap: 'cpr',     label: 'Dual-Frequency Confirmed Ice',           hint: '🟡 Both L-band and S-band ice criteria met — highest confidence.' },
  } : {};

  const tabMaps = activeTab === 'lband' ? lbandMaps : activeTab === 'sband' ? sbandMaps : dualMaps;

  const TABS = [
    { key: 'lband', label: '📡 L-band (24 cm)', color: 'var(--cyan)' },
    { key: 'sband', label: '📡 S-band (9 cm)',  color: '#f472b6' },
    { key: 'dual',  label: '🔀 Dual-Frequency', color: 'var(--green)' },
  ] as const;

  return (
    <>
      <div className="page-header">
        <div className="page-header-badge">📡 Dual-Frequency Polarimetric Analysis</div>
        <h1 className="page-title">DFSAR Polarimetric Analysis — L-band & S-band</h1>
        <p className="page-subtitle">Chandrayaan-2 DFSAR dual-frequency · L-band (430 MHz) + S-band (2.5 GHz) · CPR+DOP ice detection</p>
      </div>

      <div className="page-body">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
          <BandBadge label="L-band" freq="430 MHz" wl="24 cm" depth="~5 m"   color="var(--cyan)" />
          <BandBadge label="S-band" freq="2.5 GHz" wl="9 cm"  depth="~1.5 m" color="#f472b6" />
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.3)', borderRadius: 8, padding: '8px 14px', fontSize: 12, color: 'var(--text-secondary)' }}>
            💡 Dual-frequency DFR analysis eliminates rough-terrain false positives (Nozette et al. 1996)
          </div>
        </div>

        <div className="info-block">
          <strong>Scientific Criterion:</strong> CPR {'>'} 1 AND DOP {'<'} 0.13 applied independently to both L-band (24 cm, ~5 m depth) and
          S-band (9 cm, ~1.5 m depth). Dual-Frequency Ratio DFR = CPR_L/CPR_S {'>'} 1 discriminates deep subsurface ice from surface roughness.
          Temperature {'<'} 110 K applied as hard stability gate. (<strong>Putrevu et al. 2023, Chakraborty et al. 2024, Zhang & Paige 2009</strong>)
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /><span>Processing dual-frequency DFSAR data...</span></div>
        ) : data ? (
          <>
            {/* Key Stats */}
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-label">L-band Ice Pixels</div>
                <div className="stat-value" style={{ fontSize: 20, color: 'var(--cyan)' }}>{(data.n_ice_L_band ?? data.n_pixels_both)?.toLocaleString()}</div>
                <div className="stat-sub">CPR_L {'>'} 1 AND DOP_L {'<'} 0.13</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">S-band Ice Pixels</div>
                <div className="stat-value" style={{ fontSize: 20, color: '#f472b6' }}>{data.n_ice_S_band?.toLocaleString() ?? '—'}</div>
                <div className="stat-sub">CPR_S {'>'} 1 AND DOP_S {'<'} 0.13</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Dual-Confirmed Ice</div>
                <div className="stat-value" style={{ fontSize: 20, color: 'var(--green)' }}>{data.n_ice_dual_confirmed?.toLocaleString() ?? '—'}</div>
                <div className="stat-sub">Both bands agree</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Confirmation Rate</div>
                <div className="stat-value" style={{ fontSize: 20, color: 'var(--orange)' }}>{data.pct_dual_confirmed?.toFixed(1) ?? '—'}%</div>
                <div className="stat-sub">Of L-band candidates</div>
              </div>
            </div>

            {/* Band tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              {TABS.map(tab => (
                <button key={tab.key}
                  className={`btn ${activeTab === tab.key ? 'btn-primary' : 'btn-outline'}`}
                  style={{ padding: '8px 18px', fontSize: 13 }}
                  onClick={() => { setActiveTab(tab.key); setActiveMap(Object.keys(tabMaps)[0]); }}>
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              {/* Map viewer */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">🗺️ Polarimetric Maps</span>
                  <span className="badge" style={{
                    background: activeTab === 'lband' ? 'rgba(0,212,255,0.15)' : activeTab === 'sband' ? 'rgba(244,114,182,0.15)' : 'rgba(52,211,153,0.15)',
                    color: activeTab === 'lband' ? 'var(--cyan)' : activeTab === 'sband' ? '#f472b6' : 'var(--green)',
                  }}>{activeTab === 'lband' ? 'L-band' : activeTab === 'sband' ? 'S-band' : 'Dual-Freq'}</span>
                </div>
                <div className="card-body">
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                    {Object.entries(tabMaps).map(([key]) => (
                      <button key={key}
                        className={`btn ${activeMap === key ? 'btn-primary' : 'btn-outline'}`}
                        style={{ padding: '5px 12px', fontSize: 11 }}
                        onClick={() => setActiveMap(key)}>
                        {key.toUpperCase().replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                  {tabMaps[activeMap] && (
                    <Heatmap data={tabMaps[activeMap].data} colormap={tabMaps[activeMap].colormap} title={tabMaps[activeMap].label} />
                  )}
                  <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
                    {tabMaps[activeMap]?.hint}
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                  <div className="card-header"><span className="card-title" style={{ color: 'var(--cyan)' }}>📡 L-band CPR Histogram</span></div>
                  <div className="card-body">
                    <BarChart data={data.cpr_histogram} color="rgba(0,212,255,0.7)" threshold={1.0} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                      <span>0</span><span>CPR_L</span><span>3</span>
                    </div>
                    <div className="metric-row" style={{ marginTop: 8 }}>
                      <span className="label">Mean CPR_L</span>
                      <span className="value" style={{ color: 'var(--cyan)' }}>{data.cpr_stats.mean.toFixed(3)}</span>
                    </div>
                    <div className="metric-row">
                      <span className="label">Ice region CPR_L</span>
                      <span className="value" style={{ color: 'var(--cyan)' }}>{data.cpr_ice_stats.mean?.toFixed(3) ?? '—'}</span>
                    </div>
                  </div>
                </div>

                {data.cpr_s_histogram && (
                  <div className="card">
                    <div className="card-header"><span className="card-title" style={{ color: '#f472b6' }}>📡 S-band CPR Histogram</span></div>
                    <div className="card-body">
                      <BarChart data={data.cpr_s_histogram} color="rgba(244,114,182,0.7)" threshold={1.0} />
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                        <span>0</span><span>CPR_S</span><span>3</span>
                      </div>
                      <div className="metric-row" style={{ marginTop: 8 }}>
                        <span className="label">Mean CPR_S</span>
                        <span className="value" style={{ color: '#f472b6' }}>{data.cpr_s_stats?.mean?.toFixed(3) ?? '—'}</span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="card">
                  <div className="card-header"><span className="card-title">🔀 Dual-Frequency Summary</span></div>
                  <div className="card-body">
                    {[
                      { label: 'L-band ice (430 MHz)',  value: `${(data.n_ice_L_band ?? data.n_pixels_both)?.toLocaleString()} px`, color: 'var(--cyan)' },
                      { label: 'S-band ice (2.5 GHz)', value: `${data.n_ice_S_band?.toLocaleString() ?? '—'} px`,                   color: '#f472b6' },
                      { label: 'Dual confirmed',        value: `${data.n_ice_dual_confirmed?.toLocaleString() ?? '—'} px`,           color: 'var(--green)' },
                      { label: 'Confirmation rate',     value: `${data.pct_dual_confirmed?.toFixed(1) ?? '—'}%`,                    color: 'var(--orange)' },
                      { label: 'L-band depth',          value: '~5 m',   color: 'var(--cyan)' },
                      { label: 'S-band depth',          value: '~1.5 m', color: '#f472b6' },
                      { label: 'Temp gate',             value: '< 110 K (Zhang & Paige 2009)', color: 'var(--purple-bright)' },
                    ].map(row => (
                      <div key={row.label} className="metric-row">
                        <span className="label">{row.label}</span>
                        <span className="value" style={{ color: row.color }}>{row.value}</span>
                      </div>
                    ))}
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
