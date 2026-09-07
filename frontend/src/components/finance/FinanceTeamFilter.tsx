import { MenuItem, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../../api/lookups';
import { FilterSelect } from '../ui/design-system/FilterSelect';

const STORAGE_KEY = 'finance.selectedTeamId';
const FY_STORAGE_KEY = 'finance.selectedFyStartYear';

export function readStoredFinanceTeamId(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

export function writeStoredFinanceTeamId(teamId: string) {
  try {
    if (!teamId) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, teamId);
  } catch {
    /* ignore */
  }
}

export function readStoredFinanceFyStartYear(): number | null {
  try {
    const raw = localStorage.getItem(FY_STORAGE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) && n >= 2000 && n <= 2100 ? n : null;
  } catch {
    return null;
  }
}

export function writeStoredFinanceFyStartYear(year: number | null) {
  try {
    if (year == null) localStorage.removeItem(FY_STORAGE_KEY);
    else localStorage.setItem(FY_STORAGE_KEY, String(year));
  } catch {
    /* ignore */
  }
}

/** Current FY start calendar year for an April-default FY (matches backend default). */
export function inferCurrentFyStartYear(today = new Date(), fyStartMonth = 4): number {
  const y = today.getFullYear();
  const m = today.getMonth() + 1;
  return m >= fyStartMonth ? y : y - 1;
}

export function teamQueryParam(teamId: string): string {
  return teamId ? `?team_id=${encodeURIComponent(teamId)}` : '';
}

/** Build finance query string with optional team + FY start year. */
export function financeQueryParam(
  teamId: string,
  fyStartYear?: number | null,
  extra?: Record<string, string | number | null | undefined>,
): string {
  const params = new URLSearchParams();
  if (teamId) params.set('team_id', teamId);
  if (fyStartYear != null && Number.isFinite(fyStartYear)) {
    params.set('fy_start_year', String(fyStartYear));
  }
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v != null && v !== '') params.set(k, String(v));
    }
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

/** FY options: previous 3, current, next 1. */
export function financeFyOptions(fyStartMonth = 4): Array<{ value: number; label: string }> {
  const current = inferCurrentFyStartYear(new Date(), fyStartMonth);
  const opts: Array<{ value: number; label: string }> = [];
  for (let y = current - 3; y <= current + 1; y += 1) {
    const endShort = String(y + 1).slice(-2);
    opts.push({
      value: y,
      label: y === current ? `FY ${y}-${endShort} (current)` : `FY ${y}-${endShort}`,
    });
  }
  return opts;
}

interface FinanceTeamFilterProps {
  value: string;
  onChange: (teamId: string) => void;
  fyStartYear?: number | null;
  onFyStartYearChange?: (year: number | null) => void;
  fyStartMonth?: number;
}

export function FinanceTeamFilter({
  value,
  onChange,
  fyStartYear = null,
  onFyStartYearChange,
  fyStartMonth = 4,
}: FinanceTeamFilterProps) {
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const teams = teamsQuery.data ?? [];
  const fyOptions = financeFyOptions(fyStartMonth);
  const currentFy = inferCurrentFyStartYear(new Date(), fyStartMonth);
  const selectedFy = fyStartYear ?? currentFy;

  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={1.5}
      sx={{ mb: 2, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
    >
      <Typography variant="body2" color="text.secondary">
        Team lens: costs, salaries, renewals, and commercial terms are scoped to the selected team
        (shared HQ costs use Corporate / Management). Financial year drives turnover, P&amp;L, and
        cash forecast.
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ minWidth: { sm: 520 } }}>
        {onFyStartYearChange ? (
          <FilterSelect
            label="Financial year"
            value={String(selectedFy)}
            fullWidth={false}
            sx={{ minWidth: 220 }}
            onChange={(event) => {
              const next = Number(event.target.value);
              const year = next === currentFy ? null : next;
              writeStoredFinanceFyStartYear(year);
              onFyStartYearChange(year);
            }}
          >
            {fyOptions.map((opt) => (
              <MenuItem key={opt.value} value={String(opt.value)}>
                {opt.label}
              </MenuItem>
            ))}
          </FilterSelect>
        ) : null}
        <FilterSelect
          label="Team"
          value={value}
          fullWidth={false}
          sx={{ minWidth: 260 }}
          onChange={(event) => {
            const next = String(event.target.value);
            writeStoredFinanceTeamId(next);
            onChange(next);
          }}
        >
          <MenuItem value="">All teams</MenuItem>
          {teams.map((team) => (
            <MenuItem key={team.id} value={team.id}>
              {team.name}
            </MenuItem>
          ))}
        </FilterSelect>
      </Stack>
    </Stack>
  );
}
