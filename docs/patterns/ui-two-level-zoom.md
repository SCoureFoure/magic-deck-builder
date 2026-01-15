# UI: Two-Level Zoom Interaction

## Context
Use this pattern when users need to inspect small images (card art, thumbnails, etc.) at multiple detail levels without leaving the current view. Provides quick preview on hover and detailed inspection on click.

## Implementation
**State management:**
- Track which item is locked at max zoom via React state
- Single item can be zoomed at a time

**CSS approach:**
- Base state: normal size with `cursor: pointer`
- Hover state: `transform: scale(2.5)` with elevated z-index (150)
- Clicked/zoomed state: `transform: scale(4)` with highest z-index (200)
- Use `transform-origin: left center` to anchor scaling
- Smooth transitions (0.3s ease) for polish
- Stabilize GPU rendering with `transform: translateZ(0)`, `backface-visibility: hidden`, and `will-change: transform`

**Event handling:**
- `onClick`: Toggle zoom state for clicked item, use `event.stopPropagation()` to prevent bubbling
- `useEffect` with document-level `pointerdown` listener (only while zoomed): Clear zoom when clicking outside
- Check `event.target.closest(".card-image")` to exclude clicks on the zoomed image itself
- `onMouseLeave`: Clear zoom when mouse leaves zoomed image (provides intuitive exit)

**Key technical decisions:**
- z-index layering: base=1, hover=150, zoomed=200 ensures proper stacking
- Document listener in capture phase (`true` flag) to intercept before React synthetic events
- Cleanup listener in useEffect return to prevent memory leaks

## Trade-offs
**Optimizes for:**
- Quick inspection without navigation
- Mobile-friendly (works with touch/pointer events)
- Keeps user context in results list

**Sacrifices:**
- No pan/drag on zoomed image
- Single zoom at a time (not simultaneous comparison)
- Requires adequate viewport space (zoomed image can extend beyond container)

## Examples
- [web/src/App.tsx:36-70](web/src/App.tsx) - State management and event handlers
- [web/src/App.tsx:203-211](web/src/App.tsx) - Image element with zoom handlers
- [web/src/styles.css:245-273](web/src/styles.css) - CSS zoom implementation

## Updated
2026-01-14: Initial pattern documentation
2026-01-14: Synced references and clarified pointerdown lifecycle
2026-01-14: Documented GPU-stabilized transform settings to prevent image tearing
