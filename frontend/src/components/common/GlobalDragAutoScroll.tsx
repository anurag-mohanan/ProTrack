import { useEffect } from 'react';
import { installDragAutoScroll } from '../../utils/dragAutoScroll';

/**
 * Enables viewport-edge auto-scroll during any HTML5 drag-and-drop
 * across the app (org chart, resource planning, template editor, etc.).
 */
export function useGlobalDragAutoScroll() {
  useEffect(() => installDragAutoScroll(), []);
}

/** Mount once near the app root. */
export function GlobalDragAutoScroll() {
  useGlobalDragAutoScroll();
  return null;
}
