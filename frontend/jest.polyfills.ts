/**
 * Fetch API polyfills for Jest (jsdom environment).
 *
 * Listed in jest.config.ts `setupFiles` so it runs BEFORE any test framework
 * or module imports, ensuring MSW 2.x / @mswjs/interceptors can initialize.
 *
 * Node 18+ has native Fetch globals but jsdom resets them. Re-expose them here.
 */

// @ts-expect-error — accessing Node.js built-in globals through any
const nodeGlobals = global as Record<string, unknown>;

if (typeof globalThis.Request === "undefined") {
  globalThis.Request = nodeGlobals["Request"] as typeof Request;
}
if (typeof globalThis.Response === "undefined") {
  globalThis.Response = nodeGlobals["Response"] as typeof Response;
}
if (typeof globalThis.Headers === "undefined") {
  globalThis.Headers = nodeGlobals["Headers"] as typeof Headers;
}
if (typeof globalThis.fetch === "undefined") {
  globalThis.fetch = nodeGlobals["fetch"] as typeof fetch;
}
if (typeof globalThis.ReadableStream === "undefined") {
  globalThis.ReadableStream = nodeGlobals["ReadableStream"] as typeof ReadableStream;
}
