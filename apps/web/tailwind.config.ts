import type { Config } from "tailwindcss";
import { colors, radii, shadows, motion } from "@meta-supreme/ui";

/**
 * The theme is READ from @meta-supreme/ui, not restated here.
 *
 * This file previously carried its own copy of every hex, which meant the
 * tokens package and the thing that actually renders could disagree without
 * anything failing — the worst kind of drift, because it looks fine in review.
 * There is one source now; changing a token changes the product.
 */
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
        navy: colors.navy,
        amber: colors.amber,
        surface: colors.surface,
        border: colors.border,
      },
      borderRadius: radii,
      boxShadow: shadows,
      transitionDuration: {
        fast: motion.fast,
        normal: motion.normal,
        slow: motion.slow,
      },
      transitionTimingFunction: {
        flagship: motion.easing,
      },
    },
  },
  plugins: [],
};

export default config;
