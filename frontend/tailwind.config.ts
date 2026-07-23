import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // warm near-black elevations
        bg: "#16130f",
        panel: "#1c1813",
        surface: "#221d17",
        elevated: "#2a241c",
        // cream ink
        ink: "#ECE5D8",
        muted: "#9C9081",
        // hairlines — white @ ~10–18%
        line: "rgba(236, 229, 216, 0.10)",
        "line-strong": "rgba(236, 229, 216, 0.18)",
        // coral-amber accent (≤10% usage)
        accent: {
          DEFAULT: "#E07A4B",
          ink: "#1B1109",
          soft: "rgba(224, 122, 75, 0.12)",
        },
        // semantic only
        blue: "#7E9CB8",
        red: "#CB7A6E",
        live: "#C9A24B",
        warn: "#D8B25C",
      },
      fontFamily: {
        mono: [
          "IBM Plex Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
        ui: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      borderRadius: {
        console: "8px",
        control: "6px",
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
    },
  },
  plugins: [],
  darkMode: "class",
};
export default config;
