/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: 'var(--surface)',
          light: 'var(--surface-light)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          active: 'var(--primary-active)',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          hover: 'var(--secondary-hover)',
        },
        success: {
          DEFAULT: 'var(--success)',
          bg: 'var(--success-bg)',
          border: 'var(--success-border)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          bg: 'var(--warning-bg)',
          border: 'var(--warning-border)',
        },
        danger: {
          DEFAULT: 'var(--danger)',
          bg: 'var(--danger-bg)',
          border: 'var(--danger-border)',
        },
        info: {
          DEFAULT: 'var(--info)',
          bg: 'var(--info-bg)',
          border: 'var(--info-border)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          DEFAULT: 'var(--border-default)',
        },
      },
      boxShadow: {
        'neu-raised': 'var(--neu-raised)',
        'neu-inset': 'var(--neu-inset)',
        'neu-flat': 'var(--neu-flat)',
        'neu-hover': 'var(--neu-hover)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      spacing: {
        xs: 'var(--space-xs)',
        sm: 'var(--space-sm)',
        md: 'var(--space-md)',
        lg: 'var(--space-lg)',
        xl: 'var(--space-xl)',
      },
      minHeight: {
        'tap': '44px',
      },
      minWidth: {
        'tap': '44px',
      },
    },
  },
  plugins: [],
}
