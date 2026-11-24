// React Navigation UiKit item has 5px padding on each edge. Reserve its full
// glyph + scaled label + padding, independently from Android's bottom inset.
export function tabBarHeight(fontScale: number, bottomInset: number) {
  return Math.ceil(
    28 + 15 * Math.max(1, fontScale) + 10 + 6 + Math.max(8, bottomInset) + 3,
  );
}
