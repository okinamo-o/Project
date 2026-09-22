/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: "#040711",
          900: "#070C1B",
          850: "#0B1224",
          800: "#0F182E",
          750: "#14203D",
          700: "#1A284D",
          600: "#273B6B",
        },
        space: {
          950: "#030712",
          900: "#070d1a",
          850: "#0b1324",
          800: "#0f172a",
          700: "#1e293b",
        },
        nexus: {
          bg: "#040711",
          card: "rgba(11, 18, 36, 0.72)",
          cardHover: "rgba(16, 26, 52, 0.88)",
          border: "rgba(255, 255, 255, 0.08)",
          borderGlow: "rgba(0, 242, 254, 0.35)",
          highlight: "#1e3a5f",
          accent: "#00f2fe",
        },
        prismatic: {
          cyan: "#00f2fe",
          sky: "#38bdf8",
          teal: "#14b8a6",
          indigo: "#6366f1",
          violet: "#8b5cf6",
          purple: "#a855f7",
          emerald: "#10b981",
          amber: "#f59e0b",
          orange: "#f97316",
          rose: "#f43f5e",
          crimson: "#ff2a55",
        },
        cyber: {
          cyan: "#06b6d4",
          teal: "#14b8a6",
          indigo: "#6366f1",
          violet: "#8b5cf6",
          emerald: "#10b981",
          amber: "#f59e0b",
          rose: "#f43f5e",
          crimson: "#ef4444",
        },
        status: {
          normal: "#10b981",
          attention: "#f59e0b",
          anomaly: "#f97316",
          incident: "#ff2a55",
          offline: "#64748b",
        }
      },
      fontFamily: {
        sans: ['var(--font-outfit)', 'var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        display: ['var(--font-outfit)', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan': '0 0 25px -4px rgba(0, 242, 254, 0.35)',
        'glow-cyan-sm': '0 0 15px -3px rgba(0, 242, 254, 0.3)',
        'glow-rose': '0 0 30px -4px rgba(255, 42, 85, 0.5)',
        'glow-rose-sm': '0 0 15px -3px rgba(255, 42, 85, 0.35)',
        'glow-emerald': '0 0 25px -4px rgba(16, 185, 129, 0.35)',
        'glow-emerald-sm': '0 0 14px -3px rgba(16, 185, 129, 0.3)',
        'glow-amber': '0 0 25px -4px rgba(245, 158, 11, 0.35)',
        'glow-indigo': '0 0 25px -4px rgba(99, 102, 241, 0.35)',
        'glow-violet': '0 0 25px -4px rgba(139, 92, 246, 0.35)',
        'glass-inset': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.09)',
        'glass-card': '0 12px 35px -10px rgba(0, 0, 0, 0.75), inset 0 1px 0 0 rgba(255, 255, 255, 0.08)',
        'glass-elevated': '0 20px 50px -15px rgba(0, 0, 0, 0.85), 0 0 30px -5px rgba(0, 242, 254, 0.15), inset 0 1px 0 0 rgba(255, 255, 255, 0.14)',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 14px rgba(255, 42, 85, 0.95))' },
          '50%': { opacity: '0.4', filter: 'drop-shadow(0 0 4px rgba(255, 42, 85, 0.3))' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        floatSlow: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        beaconPing: {
          '0%': { transform: 'scale(0.95)', opacity: '0.9' },
          '70%, 100%': { transform: 'scale(2.2)', opacity: '0' },
        },
        radarSweep: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' }
        }
      },
      animation: {
        'alarm-pulse': 'pulseGlow 1.1s infinite ease-in-out',
        'shimmer': 'shimmer 2.5s infinite',
        'scanline': 'scanline 8s linear infinite',
        'float': 'floatSlow 4s ease-in-out infinite',
        'beacon': 'beaconPing 2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'radar': 'radarSweep 12s linear infinite',
      }
    },
  },
  plugins: [],
}
