/**
 * Global drag auto-scroll — when HTML5 drag is active and the pointer
 * approaches the top/bottom of the viewport, scroll the page (and any
 * nested scrollable under the pointer) so drop targets off-screen become reachable.
 */

const EDGE_PX = 72;
const MAX_SPEED_PX = 28;

export type DragAutoScrollOptions = {
  edgePx?: number;
  maxSpeedPx?: number;
};

function canScrollY(el: HTMLElement): boolean {
  const style = window.getComputedStyle(el);
  const overflowY = style.overflowY;
  if (overflowY !== 'auto' && overflowY !== 'scroll' && overflowY !== 'overlay') {
    return false;
  }
  return el.scrollHeight > el.clientHeight + 1;
}

function scrollableAncestorsAt(x: number, y: number): HTMLElement[] {
  const start = document.elementFromPoint(x, y);
  const found: HTMLElement[] = [];
  let current: Element | null = start;
  while (current) {
    if (current instanceof HTMLElement && canScrollY(current)) {
      found.push(current);
    }
    current = current.parentElement;
  }
  return found;
}

function edgeDelta(clientY: number, edgePx: number, maxSpeedPx: number): number {
  const viewHeight = window.innerHeight;
  if (clientY < edgePx) {
    const intensity = Math.min(1, (edgePx - clientY) / edgePx);
    return -Math.ceil(maxSpeedPx * intensity);
  }
  if (clientY > viewHeight - edgePx) {
    const intensity = Math.min(1, (clientY - (viewHeight - edgePx)) / edgePx);
    return Math.ceil(maxSpeedPx * intensity);
  }
  return 0;
}

function applyScroll(deltaY: number, x: number, y: number): void {
  if (deltaY === 0) return;

  // Prefer the page/viewport scroll first (matches “top/bottom of screen”).
  const docEl = document.scrollingElement ?? document.documentElement;
  const beforeDoc = docEl.scrollTop;
  docEl.scrollTop += deltaY;
  let remaining = deltaY - (docEl.scrollTop - beforeDoc);

  // If the page cannot move further (or is not the scroller), scroll nested panels.
  if (remaining === 0) return;

  for (const el of scrollableAncestorsAt(x, y)) {
    if (el === docEl) continue;
    const before = el.scrollTop;
    el.scrollTop += remaining;
    remaining -= el.scrollTop - before;
    if (remaining === 0) break;
  }
}

/** Pure helper exported for tests / reuse. */
export function computeDragAutoScrollDelta(
  clientY: number,
  options: DragAutoScrollOptions = {},
): number {
  return edgeDelta(
    clientY,
    options.edgePx ?? EDGE_PX,
    options.maxSpeedPx ?? MAX_SPEED_PX,
  );
}

/**
 * Start listening for HTML5 drag events on the document.
 * Returns a disposer. Safe to call once at app root.
 */
export function installDragAutoScroll(options: DragAutoScrollOptions = {}): () => void {
  const edgePx = options.edgePx ?? EDGE_PX;
  const maxSpeedPx = options.maxSpeedPx ?? MAX_SPEED_PX;

  let dragging = false;
  let pointerX = 0;
  let pointerY = 0;
  let rafId = 0;

  const stopLoop = () => {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = 0;
    }
  };

  const tick = () => {
    if (!dragging) {
      rafId = 0;
      return;
    }
    const delta = edgeDelta(pointerY, edgePx, maxSpeedPx);
    if (delta !== 0) {
      applyScroll(delta, pointerX, pointerY);
    }
    rafId = requestAnimationFrame(tick);
  };

  const ensureLoop = () => {
    if (!rafId) {
      rafId = requestAnimationFrame(tick);
    }
  };

  const onDragStart = (event: DragEvent) => {
    // Ignore file drags from OS into file inputs unless they have local payload —
    // still useful to scroll while rearranging; enable for all dragstart.
    dragging = true;
    pointerX = event.clientX;
    pointerY = event.clientY;
    ensureLoop();
  };

  const onDragOver = (event: DragEvent) => {
    if (!dragging) {
      // Some browsers omit dragstart for certain sources; treat dragover as active.
      dragging = true;
      ensureLoop();
    }
    pointerX = event.clientX;
    pointerY = event.clientY;
  };

  const onDrag = (event: DragEvent) => {
    if (event.clientX === 0 && event.clientY === 0) return;
    pointerX = event.clientX;
    pointerY = event.clientY;
  };

  const endDrag = () => {
    dragging = false;
    stopLoop();
  };

  document.addEventListener('dragstart', onDragStart, true);
  document.addEventListener('drag', onDrag, true);
  document.addEventListener('dragover', onDragOver, true);
  document.addEventListener('dragend', endDrag, true);
  document.addEventListener('drop', endDrag, true);

  return () => {
    endDrag();
    document.removeEventListener('dragstart', onDragStart, true);
    document.removeEventListener('drag', onDrag, true);
    document.removeEventListener('dragover', onDragOver, true);
    document.removeEventListener('dragend', endDrag, true);
    document.removeEventListener('drop', endDrag, true);
  };
}
