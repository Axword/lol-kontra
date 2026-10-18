import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        panel2: "var(--panel-2)",
        line: "var(--line)",
        lineSoft: "var(--line-soft)",
        ink: "var(--text)",
        dim: "var(--text-dim)",
        faint: "var(--text-faint)",
        gold: {
          DEFAULT: "var(--gold)",
          dim: "var(--gold-dim)",
          lite: "var(--gold-lite)",
        },
        ok: "var(--ok)",
        bad: "var(--bad)",
        rarity: {
          common: "var(--rarity-common)",
          rare: "var(--rarity-rare)",
          epic: "var(--rarity-epic)",
          legendary: "var(--rarity-legendary)",
          diamond: "var(--rarity-diamond)",
        },
      },
      fontFamily: {
        display: ['Arial', 'Helvetica', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        wider2: '0.18em',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
};
export default config;
