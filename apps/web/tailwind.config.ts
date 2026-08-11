import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#0A1628",
          50: "#E8EDF4",
          100: "#C5D0E0",
          200: "#9AADC8",
          300: "#6E8AAF",
          400: "#4A6B96",
          500: "#2C4A78",
          600: "#1E365C",
          700: "#152742",
          800: "#0F1C30",
          900: "#0A1628",
          950: "#060E1A",
        },
        amber: {
          DEFAULT: "#D4A017",
          50: "#FBF6E9",
          100: "#F5EBC7",
          200: "#ECD98A",
          300: "#E2C44D",
          400: "#D4A017",
          500: "#B8860B",
          600: "#9A6F09",
          700: "#7C5807",
          800: "#5E4205",
          900: "#402C03",
        },
        surface: {
          DEFAULT: "#F8F5F0",
          muted: "#F0EBE3",
          elevated: "#FFFFFF",
        },
        border: {
          DEFAULT: "#E5DFD5",
          strong: "#D4CBBC",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      boxShadow: {
        soft: "0 2px 8px -2px rgba(10, 22, 40, 0.08), 0 4px 16px -4px rgba(10, 22, 40, 0.06)",
        elevated:
          "0 8px 24px -4px rgba(10, 22, 40, 0.12), 0 4px 12px -2px rgba(10, 22, 40, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
