'use client';
import { useEffect, useRef } from 'react';

interface HeatmapProps {
  data: number[][];
  colormap?: 'viridis' | 'plasma' | 'ice' | 'shadow' | 'cpr' | 'dop' | 'slope' | 'prob';
  width?: number;
  height?: number;
  overlayPoints?: { row: number; col: number; color: string; size?: number; label?: string }[];
  overlayPath?: { row: number; col: number }[];
  title?: string;
  minVal?: number;
  maxVal?: number;
}

// Colormaps as RGB stops [value_0_to_1 → [r,g,b]]
const COLORMAPS: Record<string, [number, number, number][]> = {
  viridis: [
    [68, 1, 84], [58, 82, 139], [32, 144, 140], [94, 201, 97], [253, 231, 36]
  ],
  plasma: [
    [13, 8, 135], [126, 3, 168], [204, 71, 120], [248, 149, 64], [240, 249, 33]
  ],
  ice: [
    [0, 20, 60], [0, 80, 140], [0, 180, 220], [100, 230, 255], [220, 245, 255]
  ],
  shadow: [
    [5, 10, 20], [10, 25, 50], [15, 40, 80], [30, 70, 120], [60, 120, 180]
  ],
  cpr: [
    [5, 10, 30], [20, 60, 120], [0, 150, 200], [255, 160, 0], [255, 50, 50]
  ],
  dop: [
    [220, 50, 50], [200, 150, 0], [50, 180, 80], [0, 150, 220], [10, 20, 60]
  ],
  slope: [
    [5, 100, 50], [80, 180, 50], [220, 200, 10], [240, 120, 10], [200, 20, 20]
  ],
  prob: [
    [5, 5, 20], [20, 20, 80], [0, 80, 160], [0, 200, 255], [255, 255, 100]
  ],
};

function interpolateColor(stops: [number, number, number][], t: number): [number, number, number] {
  t = Math.max(0, Math.min(1, t));
  const n = stops.length - 1;
  const i = Math.floor(t * n);
  const f = t * n - i;
  if (i >= n) return stops[n];
  const a = stops[i], b = stops[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
  ];
}

export default function Heatmap({
  data, colormap = 'viridis', width = 256, height = 256,
  overlayPoints = [], overlayPath = [], title, minVal, maxVal
}: HeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!data || data.length === 0 || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rows = data.length;
    const cols = data[0].length;
    canvas.width = cols;
    canvas.height = rows;

    // Compute min/max
    let dmin = minVal ?? Infinity;
    let dmax = maxVal ?? -Infinity;
    if (minVal === undefined || maxVal === undefined) {
      for (const row of data) {
        for (const v of row) {
          if (isFinite(v)) {
            if (v < dmin) dmin = v;
            if (v > dmax) dmax = v;
          }
        }
      }
    }
    const range = dmax - dmin || 1;

    const imageData = ctx.createImageData(cols, rows);
    const stops = COLORMAPS[colormap] || COLORMAPS.viridis;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const t = (data[r][c] - dmin) / range;
        const [red, green, blue] = interpolateColor(stops, t);
        const idx = (r * cols + c) * 4;
        imageData.data[idx] = red;
        imageData.data[idx + 1] = green;
        imageData.data[idx + 2] = blue;
        imageData.data[idx + 3] = 255;
      }
    }
    ctx.putImageData(imageData, 0, 0);

    // Draw path
    if (overlayPath.length > 1) {
      const scaleR = rows / rows;
      const scaleC = cols / cols;
      ctx.beginPath();
      ctx.strokeStyle = '#00ffff';
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 2]);
      overlayPath.forEach((p, i) => {
        const x = p.col * scaleC;
        const y = p.row * scaleR;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw overlay points
    overlayPoints.forEach(pt => {
      const x = pt.col;
      const y = pt.row;
      const size = pt.size ?? 6;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = pt.color;
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      if (pt.label) {
        ctx.fillStyle = 'white';
        ctx.font = 'bold 9px sans-serif';
        ctx.fillText(pt.label, x + size + 2, y + 3);
      }
    });
  }, [data, colormap, overlayPoints, overlayPath, minVal, maxVal]);

  return (
    <div className="heatmap-container" style={{ position: 'relative' }}>
      {title && (
        <div style={{
          position: 'absolute', top: 8, left: 10, zIndex: 10,
          background: 'rgba(0,0,0,0.7)', padding: '3px 8px',
          borderRadius: 6, fontSize: 11, color: '#94b8d4', fontWeight: 600
        }}>
          {title}
        </div>
      )}
      <canvas
        ref={canvasRef}
        className="heatmap-canvas"
        style={{ imageRendering: 'pixelated' }}
      />
    </div>
  );
}
