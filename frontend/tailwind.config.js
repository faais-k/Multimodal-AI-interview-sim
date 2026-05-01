/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Ascent AI Design System
        surface: {
          base: "#FAFAF8",
          raised: "#FFFFFF",
          overlay: "#F0EFEA",
        },
        text: {
          primary: "#1A1A18",
          secondary: "#6B6B66",
          muted: "#9B9B95",
          disabled: "#B8B8B3",
        },
        "ascent-blue": {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
          subtle: "#DBEAFE",
          muted: "#93C5FD",
        },
        semantic: {
          error: "#DC2626",
          "error-bg": "#FEE2E2",
          warning: "#D97706",
          "warning-bg": "#FEF3C7",
          success: "#2563EB",
          "success-bg": "#DBEAFE",
          info: "#6B6B66",
        },
        border: {
          DEFAULT: "#E5E4DF",
          subtle: "#F0EFEA",
          strong: "#D1D0CC",
        },
        // shadcn compatibility
        background: "#FAFAF8",
        foreground: "#1A1A18",
        primary: {
          DEFAULT: "#2563EB",
          foreground: "#FFFFFF",
          hover: "#1D4ED8",
        },
        secondary: {
          DEFAULT: "#F0EFEA",
          foreground: "#1A1A18",
        },
        muted: {
          DEFAULT: "#F0EFEA",
          foreground: "#6B6B66",
        },
        accent: {
          DEFAULT: "#DBEAFE",
          foreground: "#2563EB",
        },
        destructive: {
          DEFAULT: "#DC2626",
          foreground: "#FFFFFF",
        },
        card: {
          DEFAULT: "#FFFFFF",
          foreground: "#1A1A18",
        },
        popover: {
          DEFAULT: "#FFFFFF",
          foreground: "#1A1A18",
        },
        ring: "#2563EB",
        input: "#E5E4DF",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Monaco", "monospace"],
      },
      fontSize: {
        xs: ["12px", { lineHeight: "16px" }],
        sm: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        md: ["18px", { lineHeight: "28px" }],
        lg: ["20px", { lineHeight: "30px" }],
        xl: ["24px", { lineHeight: "32px" }],
        "2xl": ["32px", { lineHeight: "40px" }],
        "3xl": ["40px", { lineHeight: "48px" }],
      },
      spacing: {
        0: "0px",
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
        10: "40px",
        12: "48px",
        16: "64px",
      },
      borderRadius: {
        none: "0px",
        sm: "4px",
        DEFAULT: "6px",
        md: "6px",
        lg: "8px",
        full: "9999px",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        "out-back": "cubic-bezier(0.34, 1.56, 0.64, 1)",
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      transitionDuration: {
        fast: "150ms",
        DEFAULT: "250ms",
        slow: "400ms",
        reveal: "800ms",
      },
      keyframes: {
        "enter": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "pulse-ring": {
          "0%, 100%": { transform: "scale(1)", opacity: "0.4" },
          "50%": { transform: "scale(1.15)", opacity: "0.8" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "breathe": {
          "0%, 100%": { transform: "scale(1)", opacity: "0.3" },
          "50%": { transform: "scale(1.3)", opacity: "0.6" },
        },
        "orbit": {
          "0%": { transform: "rotate(0deg) translateX(40px) rotate(0deg)" },
          "100%": { transform: "rotate(360deg) translateX(40px) rotate(-360deg)" },
        },
        "ping": {
          "75%, 100%": { transform: "scale(2)", opacity: "0" },
        },
        "progress": {
          "0%": { width: "0%" },
          "100%": { width: "var(--progress-width, 100%)" },
        },
      },
      animation: {
        "enter": "enter 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "fade-in": "fade-in 0.3s ease forwards",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "scale-in": "scale-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "pulse-ring": "pulse-ring 2.4s ease-in-out infinite",
        "spin-slow": "spin-slow 3s linear infinite",
        "breathe": "breathe 2.4s ease-in-out infinite",
        "orbit": "orbit 3s linear infinite",
        "ping": "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
        "progress": "progress 1s ease-out forwards",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
