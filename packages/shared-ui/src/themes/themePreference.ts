// =============================================================================
// Theme Preference Resolution
// =============================================================================
// The single source of truth for which theme wins at boot and after login:
//
//   explicit local device choice  >  server account theme  >  fallback
//
// The local choice lives in two localStorage keys that must stay in lockstep:
//   rr:theme       — full theme id, written on every explicit pick
//   rr:home:theme  — 'light'/'dark' mode hint, needed by home-ui before the
//                    shell has applied any tokens (and by the inline FOUC
//                    script in shell-ui/index.html, which mirrors this logic
//                    because it cannot import modules)
//
// Every resolver (index.html FOUC script, createShellConfig.onInit, the
// post-auth restore in connection.ts, and the workspace disk merge) must
// agree on this precedence — divergence is what caused the visible
// light→dark theme flip on login.
// =============================================================================

export const DEFAULT_THEME_ID = 'rocketride-light';

// Must match the JSON files in apps/shell-ui/public/themes/. A theme id not
// in this list is treated as corrupted and falls through to the next source,
// so add new theme files here or they will never restore.
export const KNOWN_THEME_IDS = [
	'rocketride-light',
	'light',
	'dark',
	'gray',
	'rocketride',
	'visual-studio',
] as const;

const LIGHT_THEME_IDS: readonly string[] = ['rocketride-light', 'light'];

export type ThemeMode = 'light' | 'dark';

export const isKnownThemeId = (id: string | null | undefined): id is string =>
	!!id && (KNOWN_THEME_IDS as readonly string[]).includes(id);

/** home-ui only knows light/dark; the shell owns the full palette set. */
export const themeIdForMode = (mode: ThemeMode): string =>
	mode === 'dark' ? 'rocketride' : DEFAULT_THEME_ID;

export const themeModeForId = (id: string): ThemeMode =>
	LIGHT_THEME_IDS.includes(id) ? 'light' : 'dark';

/**
 * The user's explicit local device choice, or null when none exists.
 * 'rr:theme' is primary (written on every explicit pick, including home-ui
 * toggles, which route through the shell's setTheme); 'rr:home:theme' is a
 * mode-hint fallback for sessions predating the key sync.
 */
export function readLocalThemeChoice(): string | null {
	try {
		const id = localStorage.getItem('rr:theme');
		if (isKnownThemeId(id)) return id;
		const mode = localStorage.getItem('rr:home:theme');
		if (mode === 'dark' || mode === 'light') return themeIdForMode(mode);
	} catch { /* no localStorage (privacy mode) — treat as no choice */ }
	return null;
}

/** Persist an explicit pick to BOTH keys so they can never diverge. */
export function persistLocalThemeChoice(themeId: string): void {
	try {
		localStorage.setItem('rr:theme', themeId);
		localStorage.setItem('rr:home:theme', themeModeForId(themeId));
	} catch { /* non-fatal */ }
}

export interface ResolvedTheme {
	theme: string;
	source: 'local' | 'server' | 'fallback';
}

/** THE precedence rule: local choice > server account theme > fallback. */
export function resolveThemePreference(
	serverTheme?: string | null,
	fallback: string = DEFAULT_THEME_ID,
): ResolvedTheme {
	const local = readLocalThemeChoice();
	if (local) return { theme: local, source: 'local' };
	if (isKnownThemeId(serverTheme)) return { theme: serverTheme, source: 'server' };
	return { theme: fallback, source: 'fallback' };
}
