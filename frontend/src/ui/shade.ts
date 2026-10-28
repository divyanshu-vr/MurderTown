/**
 * A heatmap cell's colours: one hue over the page, deeper for more Suspicion, with black or white
 * text, whichever reads better on it. Switching where the shade's luminance crosses about 0.18
 * keeps the text at 4.5:1 contrast or more at every level.
 */
type Rgb = readonly [number, number, number];

const AMBER: Rgb = [251, 191, 36];
const PAGE: Rgb = [12, 10, 9];

/** WCAG relative luminance. */
function luminance([r, g, b]: Rgb): number {
  const linear = (channel: number) => {
    const c = channel / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

export function shadeOf(suspicion: number): { background: string; text: string } {
  const share = suspicion / 100;
  const blended = AMBER.map((channel, i) => Math.round(channel * share + (PAGE[i] ?? 0) * (1 - share))) as unknown as Rgb;
  return {
    background: `rgb(${blended.join(" ")})`,
    text: luminance(blended) > 0.179 ? "#000" : "#fff",
  };
}
