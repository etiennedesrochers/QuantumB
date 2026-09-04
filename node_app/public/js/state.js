/** Tiny shared store: caches library data used by more than one page. */

const state = {
  compressors: null,
  templates: null,
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function get(key) {
  return state[key];
}

export function set(key, value) {
  state[key] = value;
  for (const fn of listeners) fn(key, value);
  return value;
}

export function invalidate(key) {
  set(key, null);
}

/** Return the cached value, loading it once via `loader` if needed. */
export async function cached(key, loader) {
  if (state[key] === null || state[key] === undefined) set(key, await loader());
  return state[key];
}
