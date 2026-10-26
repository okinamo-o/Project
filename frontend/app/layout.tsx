import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NEXUS — Smart Building Digital Twin',
  description: 'Interactive 3D Building Monitor, Live Sensors, Forecast & AI Assistant',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="daylight" className="scroll-smooth">
      <body className="min-h-screen antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
