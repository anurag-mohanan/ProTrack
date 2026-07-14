/** Per-room Planning Board team filter — device-local for wall TVs. */

const STORAGE_KEY = 'planningBoard.roomTeamIds';
const ROOM_NAME_KEY = 'planningBoard.roomName';

export function loadRoomTeamIds(): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    return parsed.map(String);
  } catch {
    return null;
  }
}

export function saveRoomTeamIds(ids: string[] | null): void {
  if (!ids || ids.length === 0) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

export function loadRoomName(): string {
  try {
    return localStorage.getItem(ROOM_NAME_KEY)?.trim() || '';
  } catch {
    return '';
  }
}

export function saveRoomName(name: string): void {
  const trimmed = name.trim();
  if (!trimmed) {
    localStorage.removeItem(ROOM_NAME_KEY);
    return;
  }
  localStorage.setItem(ROOM_NAME_KEY, trimmed);
}

/** Prefer URL `?teams=id1,id2` then localStorage; null means all company teams. */
export function resolveRoomTeamIdsFromSearch(search: string): string[] | null {
  const params = new URLSearchParams(search);
  const fromUrl = params.get('teams');
  if (fromUrl != null && fromUrl.trim() !== '') {
    const ids = fromUrl
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean);
    return ids.length ? ids : null;
  }
  return loadRoomTeamIds();
}

export function buildTeamsSearchParam(ids: string[] | null): string {
  if (!ids || ids.length === 0) return '';
  return ids.join(',');
}
