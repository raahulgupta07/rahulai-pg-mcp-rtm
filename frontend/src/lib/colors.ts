export const CLASS_COLORS: Record<string, string> = {
  'Class A': '#007518',
  'Class B': '#ff9d00',
  'Class C': '#be2d06',
  'Class A Local (F4)': '#006f7c',
};

export const GROWTH_COLORS: Record<string, string> = {
  Growing: '#007518',
  Stable: '#ff9d00',
  Declining: '#be2d06',
};

export const RISK_COLORS: Record<string, string> = {
  Low: '#007518',
  Medium: '#ff9d00',
  High: '#be2d06',
};

export function classColor(cls: string): string {
  if (cls.includes('F4') || cls.includes('Local')) return CLASS_COLORS['Class A Local (F4)'];
  if (cls.includes('A')) return CLASS_COLORS['Class A'];
  if (cls.includes('B')) return CLASS_COLORS['Class B'];
  if (cls.includes('C')) return CLASS_COLORS['Class C'];
  return '#65655e';
}
