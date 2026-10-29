import { useMemo, useState } from 'react';
import type { PerformancePeriodType } from '../../types/EngineeringPerformance';
import { defaultAnchorForPeriod, toIsoDate } from '../../utils/reportPeriodSelection';
import { syncAnchorForPeriodChange } from './ReportPeriodSelectors';
import { fyQuarterFor, fyQuarterStart, fyStartYearFor } from './reportFormat';

export interface PerformancePeriodParams {
  period_type: PerformancePeriodType;
  anchor?: string;
  start_date?: string;
  end_date?: string;
}

/** Period selection shared by the completed-project reports (financial quarters/years). */
export function usePerformancePeriod(fyStartMonth: number, initial: PerformancePeriodType = 'quarterly') {
  const today = useMemo(() => new Date(), []);
  const [periodType, setPeriodType] = useState<PerformancePeriodType>(initial);
  const [anchor, setAnchor] = useState(defaultAnchorForPeriod('monthly'));
  const [fyYear, setFyYear] = useState<number | null>(null);
  const [fyQuarter, setFyQuarter] = useState<number | null>(null);
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  const selectedFyYear = fyYear ?? fyStartYearFor(today, fyStartMonth);
  const selectedFyQuarter = fyQuarter ?? fyQuarterFor(today, fyStartMonth);
  const currentFy = fyStartYearFor(today, fyStartMonth);
  const fyYears = Array.from({ length: 7 }, (_, index) => currentFy + 1 - index);

  const customRangeError =
    periodType === 'custom'
      ? !customStart || !customEnd
        ? 'Choose a start and end date.'
        : customEnd < customStart
          ? 'End date must be on or after the start date.'
          : null
      : null;

  const params = useMemo<PerformancePeriodParams>(() => {
    if (periodType === 'custom') {
      return { period_type: periodType, start_date: customStart, end_date: customEnd };
    }
    if (periodType === 'quarterly') {
      return {
        period_type: periodType,
        anchor: toIsoDate(fyQuarterStart(selectedFyYear, selectedFyQuarter, fyStartMonth)),
      };
    }
    if (periodType === 'yearly') {
      return { period_type: periodType, anchor: toIsoDate(new Date(selectedFyYear, fyStartMonth - 1, 1)) };
    }
    return { period_type: periodType, anchor };
  }, [periodType, customStart, customEnd, selectedFyYear, selectedFyQuarter, fyStartMonth, anchor]);

  const changePeriodType = (next: PerformancePeriodType) => {
    setPeriodType(next);
    if (next === 'weekly' || next === 'monthly') {
      setAnchor((current) => syncAnchorForPeriodChange(next, current));
    }
  };

  return {
    fyStartMonth,
    periodType,
    changePeriodType,
    anchor,
    setAnchor,
    selectedFyYear,
    setFyYear,
    selectedFyQuarter,
    setFyQuarter,
    fyYears,
    customStart,
    setCustomStart,
    customEnd,
    setCustomEnd,
    customRangeError,
    params,
  };
}

export type PerformancePeriodState = ReturnType<typeof usePerformancePeriod>;
