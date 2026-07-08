import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        lol: {
          bg: "#0A0E13",
          bg2: "#111822",
          gold: "#C89B3C",
          blue: "#0AC8B9",
          text: "#E8E6E3",
          muted: "#8A8F98"
        },
        rarity: {
          common: "#9CA3AF",
          rare: "#3B82F6",
          epic: "#A855F7",
          legendary: "#F59E0B",
          diamond: "#22D3EE"
        }
      },
      boxShadow: {
        'gold': '0 0 20px rgba(200,155,60,0.25)'
      },
      animation: {
        'pulse-gold': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
  darkMode: 'class',
};
export default config;
