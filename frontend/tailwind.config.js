/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0e14",
          900: "#0e131b",
          850: "#121925",
          800: "#172030",
          700: "#1f2a3c",
          600: "#2b384d",
          500: "#3b4a62",
        },
        fg: { DEFAULT: "#e6ebf2", muted: "#9aa7b8", dim: "#6b788b" },
        accent: { DEFAULT: "#5eb1bf", soft: "#2c5d66" },
        heat: "#e8774a",
        flood: "#4f8fd9",
        urban: "#c9a46b",
        infra: "#9a8fd1",
        vuln: "#d65b72",
        ok: "#6bbf8a",
        warn: "#d9b44a",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
    },
  },
  plugins: [],
};
