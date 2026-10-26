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
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        display: ['var(--font-display)', 'system-ui', 'sans-serif'],
      },
      colors: {
        carbon: {
          950: '#050504',
          900: '#0a0a09',
          850: '#10100e',
          800: '#161613',
          700: '#22221e',
          600: '#33332d',
        },
        signal: {
          orange: '#ff4d00',
          volt: '#c8ff00',
          amber: '#ffb000',
          crimson: '#ff1f4b',
          bone: '#f3efe6',
          ash: '#9e9a90',
        }
      }
    },
  },
  plugins: [],
};
