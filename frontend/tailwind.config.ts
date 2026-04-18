import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#11233b",
        mist: "#f4f7fb",
        accent: "#f97316",
        pine: "#166534",
        warning: "#b45309",
        danger: "#b91c1c",
      },
      boxShadow: {
        panel: "0 18px 45px -24px rgba(17, 35, 59, 0.35)",
      },
    },
  },
  plugins: [],
} satisfies Config;
