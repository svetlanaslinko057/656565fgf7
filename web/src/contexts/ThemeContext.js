import { createContext, useContext, useEffect } from 'react';

/**
 * ThemeContext — locked to DARK to match the mobile app exactly.
 *
 * The platform's design system lives in `/app/frontend/src/theme.ts` (mobile)
 * and is mirrored 1:1 in `index.css` `.dark` block. Light mode is intentionally
 * disabled here: admin/web/mobile must look the same so users don't context-shift.
 */
const ThemeContext = createContext({
  theme: 'dark',
  toggleTheme: () => {},
  setLightTheme: () => {},
  setDarkTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('light');
    root.classList.add('dark');
    // Wipe any stale "light" preference left over from earlier builds
    try { localStorage.setItem('atlas-theme', 'dark'); } catch (_e) { /* ignore */ }
  }, []);

  // No-op setters — kept for backward compatibility with components
  // that still call toggleTheme(). They can no longer flip to light.
  return (
    <ThemeContext.Provider
      value={{
        theme: 'dark',
        toggleTheme: () => {},
        setLightTheme: () => {},
        setDarkTheme: () => {},
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};
