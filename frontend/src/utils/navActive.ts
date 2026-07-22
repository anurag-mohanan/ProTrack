/** True when another nav path is nested under ``path`` (e.g. /hr vs /hr/onboarding). */
export function navItemNeedsExactMatch(path: string, siblingPaths: readonly string[]): boolean {
  const normalized = path.replace(/\/+$/, '') || '/';
  return siblingPaths.some((other) => {
    const candidate = other.replace(/\/+$/, '') || '/';
    return candidate !== normalized && candidate.startsWith(`${normalized}/`);
  });
}
