/** Normalize FastAPI / Axios error payloads into a toast-safe string. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const parts = detail.map((item) => {
      if (typeof item === 'string') return item;
      if (item && typeof item === 'object' && 'msg' in item) {
        const loc = Array.isArray((item as { loc?: unknown }).loc)
          ? (item as { loc: unknown[] }).loc.filter((x) => x !== 'body').join('.')
          : '';
        const msg = String((item as { msg: unknown }).msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return null;
    });
    const joined = parts.filter(Boolean).join('; ');
    if (joined) return joined;
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const msg = String((detail as { message: unknown }).message);
    if (msg.trim()) return msg;
  }
  const message = (error as { message?: string })?.message;
  if (typeof message === 'string' && message.trim()) return message;
  return fallback;
}
