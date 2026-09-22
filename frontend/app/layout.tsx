import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NEXUS — Multimodal AI Digital Twin Operations Center',
  description: 'Intelligent Environmental Monitoring, Predictive Analytics and Autonomous Incident Fusion',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className="ambient-mesh min-h-screen text-slate-100 antialiased selection:bg-cyan-500 selection:text-black font-sans">
        {children}
      </body>
    </html>
  );
}
