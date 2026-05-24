/**
 * PulseDebug AI — Tailwind CSS Configuration
 * File: frontend/tailwind.config.ts
 * Purpose:
 *   Extends Tailwind with custom design tokens for the PulseDebug dashboard.
 *   Terminal/IDE-inspired dark palette with electric accent colours.
 */

import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT:   "#0d1117",
          secondary: "#161b22",
          tertiary:  "#21262d",
          border:    "#30363d",
        },
        pulse: {
          cyan:   "#00d4ff",
          green:  "#3fb950",
          yellow: "#d29922",
          red:    "#f85149",
          orange: "#fb8f44",
          purple: "#a371f7",
        },
      },
      fontFamily: {
        mono:    ["'JetBrains Mono'", "Menlo", "Monaco", "monospace"],
        sans:    ["'DM Sans'", "system-ui", "sans-serif"],
        display: ["'Space Grotesk'", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in":    "fadeIn 0.3s ease-in-out",
        "slide-up":   "slideUp 0.3s ease-out",
        "blink":      "blink 1.2s step-end infinite",
      },
      keyframes: {
        fadeIn:  { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: {
          "0%":   { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)",   opacity: "1" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;