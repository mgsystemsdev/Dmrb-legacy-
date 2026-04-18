import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "sans-serif",
        ],
      },
      colors: {
        canvas: "#0a0a0a",
        surface: {
          DEFAULT: "#111113",
          2: "#17171a",
          3: "#1f1f23",
          elevated: "#25252a",
        },
        border: {
          DEFAULT: "#26262b",
          strong: "#3a3a42",
        },
        muted: "#8b8b93",
        text: {
          DEFAULT: "#e5e5e7",
          strong: "#fafafa",
        },
        focus: "#fafafa",
        success: "#86efac",
        warning: "#fcd34d",
        danger: "#fca5a5",
      },
      borderRadius: {
        card: "14px",
      },
      boxShadow: {
        panel:
          "0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 24px 48px -24px rgba(0, 0, 0, 0.6)",
        hairline: "0 1px 0 rgba(255, 255, 255, 0.08) inset",
        "hairline-strong": "0 1px 0 rgba(255, 255, 255, 0.12) inset",
        glow: "0 0 0 1px rgba(255, 255, 255, 0.06), 0 1px 0 rgba(255, 255, 255, 0.08) inset",
      },
    },
  },
  plugins: [],
} satisfies Config;
