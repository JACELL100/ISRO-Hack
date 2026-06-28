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
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌙</text></svg>" />
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
