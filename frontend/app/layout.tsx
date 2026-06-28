import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/Sidebar';

export const metadata: Metadata = {
  title: 'ISRO Lunar Ice Explorer | BAH 2026',
  description: 'Chandrayaan-2 DFSAR/OHRC based subsurface ice detection, landing site selection, and rover traverse planning for the lunar south polar region.',
  keywords: 'ISRO, Chandrayaan-2, lunar ice, DFSAR, PSR, rover traverse, BAH 2026',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2300d4ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/></svg>" />
      </head>
      <body>
        <div className="layout-root">
          <Sidebar />
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
