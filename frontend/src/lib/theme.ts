import { writable, get } from 'svelte/store';
import { auth } from '$lib/stores/auth.svelte';

/* ============================================================
   Appearance system — mode + palette + custom accent + radius + density.
   Whole UI is driven by CSS variables, so a theme is just a set of
   variable values. Persisted to localStorage (instant) and to the
   backend per-user (follows the user across devices).
   ============================================================ */

export type Mode = 'light' | 'dark' | 'auto';
export type DensityKey = 'comfortable' | 'compact';

export interface Quad {
  accent: string;
  hover: string;
  soft: string;
  ink: string;
}

export interface Palette {
  id: string;
  name: string;
  light: Quad;
  dark: Quad;
}

export interface Appearance {
  mode: Mode;
  skin: string;          // palette id, or 'custom'
  customAccent: string;  // hex used when skin === 'custom'
  density: DensityKey;
}

const STORAGE_KEY = 'rtm-appearance';

export const DEFAULT_APPEARANCE: Appearance = {
  mode: 'auto',
  skin: 'terracotta',
  customAccent: '#C96442',
  density: 'comfortable',
};

/* ── Preset palettes ──
   Keep these in sync with the boot script in app.html (flash prevention). */
export const PALETTES: Palette[] = [
  {
    id: 'terracotta', name: 'Terracotta',
    light: { accent: '#C96442', hover: '#B5573A', soft: '#F4E4DA', ink: '#5A2B1C' },
    dark:  { accent: '#E89070', hover: '#F0A487', soft: '#3A2823', ink: '#F4E4DA' },
  },
  {
    id: 'ocean', name: 'Ocean',
    light: { accent: '#3B7EA1', hover: '#336E8D', soft: '#DEEAF0', ink: '#1B3A49' },
    dark:  { accent: '#6FAAC8', hover: '#84B9D4', soft: '#1E2E38', ink: '#DEEAF0' },
  },
  {
    id: 'forest', name: 'Forest',
    light: { accent: '#4F7A4A', hover: '#446B40', soft: '#E2EDDF', ink: '#243A22' },
    dark:  { accent: '#7FB078', hover: '#93BE8C', soft: '#233022', ink: '#E2EDDF' },
  },
  {
    id: 'violet', name: 'Violet',
    light: { accent: '#7A5CA8', hover: '#6B5096', soft: '#EAE3F2', ink: '#382A4D' },
    dark:  { accent: '#A98FD0', hover: '#B9A2DA', soft: '#2B2438', ink: '#EAE3F2' },
  },
  {
    id: 'rose', name: 'Rose',
    light: { accent: '#B5567D', hover: '#A14C6F', soft: '#F4E1E8', ink: '#4F2536' },
    dark:  { accent: '#D98AAA', hover: '#E29BB7', soft: '#36242C', ink: '#F4E1E8' },
  },
  {
    id: 'slate', name: 'Slate',
    light: { accent: '#5F5D54', hover: '#51504A', soft: '#E8E6DD', ink: '#2C2B26' },
    dark:  { accent: '#A8A39A', hover: '#B8B3AA', soft: '#33322D', ink: '#EDEAE0' },
  },
];


/* ── Color math (for the custom accent builder) ── */
function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace('#', '').trim();
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  const n = parseInt(h || 'C96442', 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function rgbToHex(r: number, g: number, b: number): string {
  const c = (x: number) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`;
}
function mix(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  return rgbToHex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t);
}

/** Derive a full accent quad from a single hex, per mode. */
export function deriveQuad(hex: string, dark: boolean): Quad {
  if (dark) {
    return {
      accent: mix(hex, '#FFFFFF', 0.24),
      hover:  mix(hex, '#FFFFFF', 0.38),
      soft:   mix(hex, '#1F1E1B', 0.80),
      ink:    mix(hex, '#FFFFFF', 0.60),
    };
  }
  return {
    accent: hex,
    hover:  mix(hex, '#000000', 0.14),
    soft:   mix(hex, '#FFFFFF', 0.84),
    ink:    mix(hex, '#000000', 0.55),
  };
}

/* ── Store ── */
export const appearance = writable<Appearance>(DEFAULT_APPEARANCE);

function readStored(): Appearance {
  if (typeof localStorage === 'undefined') return { ...DEFAULT_APPEARANCE };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_APPEARANCE, ...JSON.parse(raw) };
  } catch {}
  return { ...DEFAULT_APPEARANCE };
}

export function resolveMode(m: Mode): 'light' | 'dark' {
  if (m === 'auto') {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  }
  return m;
}

/** Resolve the accent quad for an appearance + concrete mode. */
export function quadFor(a: Appearance, dark: boolean): Quad {
  if (a.skin === 'custom') return deriveQuad(a.customAccent || DEFAULT_APPEARANCE.customAccent, dark);
  const p = PALETTES.find(p => p.id === a.skin) ?? PALETTES[0];
  return dark ? p.dark : p.light;
}

/** Write an appearance to the DOM via CSS variables + data attributes. */
export function applyAppearance(a: Appearance): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const dark = resolveMode(a.mode) === 'dark';

  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  root.setAttribute('data-density', a.density);

  const q = quadFor(a, dark);
  root.style.setProperty('--accent', q.accent);
  root.style.setProperty('--accent-hover', q.hover);
  root.style.setProperty('--accent-soft', q.soft);
  root.style.setProperty('--accent-ink', q.ink);
  root.style.setProperty('--color-primary', q.accent);
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function persist(a: Appearance): void {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(a)); } catch {}
  // Debounced server save (per-user)
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    if (!auth.token) return;
    fetch('/api/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.getHeaders() },
      body: JSON.stringify(a),
    }).catch(() => {});
  }, 600);
}

/** Update appearance — merges a partial, applies, and persists. */
export function setAppearance(patch: Partial<Appearance>): void {
  const next = { ...get(appearance), ...patch };
  appearance.set(next);
  applyAppearance(next);
  persist(next);
}

let mediaListener: ((e: MediaQueryListEvent) => void) | null = null;

/** Initialise from localStorage and start watching the OS theme. */
export function initAppearance(): void {
  if (typeof window === 'undefined') return;
  const stored = readStored();
  appearance.set(stored);
  applyAppearance(stored);

  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  if (mediaListener) mq.removeEventListener('change', mediaListener);
  mediaListener = () => { if (get(appearance).mode === 'auto') applyAppearance(get(appearance)); };
  mq.addEventListener('change', mediaListener);
}

/** Fetch the per-user appearance from the backend and apply it (call after auth). */
export async function loadServerPrefs(): Promise<void> {
  if (typeof window === 'undefined' || !auth.token) return;
  try {
    const res = await fetch('/api/preferences', { headers: auth.getHeaders() });
    if (!res.ok) return;
    const prefs = await res.json();
    if (prefs && typeof prefs === 'object' && Object.keys(prefs).length) {
      const merged = { ...DEFAULT_APPEARANCE, ...get(appearance), ...prefs };
      appearance.set(merged);
      applyAppearance(merged);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(merged)); } catch {}
    }
  } catch {}
}

/** Quick light → dark → auto cycle. */
export function cycleMode(): void {
  const cur = get(appearance).mode;
  const next: Mode = cur === 'light' ? 'dark' : cur === 'dark' ? 'auto' : 'light';
  setAppearance({ mode: next });
}

export function modeLabel(m: Mode): string {
  return m === 'light' ? 'Light' : m === 'dark' ? 'Dark' : 'Auto';
}
