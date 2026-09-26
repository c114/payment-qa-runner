import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#0f1419", card: "#1a2332", border: "#2a3548", muted: "#8b9bb4" },
        accent: { DEFAULT: "#3b82f6", good: "#22c55e", bad: "#ef4444", warn: "#f59e0b" },
      },
    },
  },
  plugins: [],
};
export default config;
