import JSDOMEnvironment from "jest-environment-jsdom";

// jsdom window does not inherit Node.js built-in globals (Request, Response, etc.).
// MSW 2.x interceptors extend the global Request class, so we must copy Node.js
// fetch globals into the jsdom window before any test module initializes.
export default class CustomJSDOMEnvironment extends JSDOMEnvironment {
  async setup() {
    await super.setup();
    const nodeGlobal = globalThis as Record<string, unknown>;
    if (typeof this.global.Request === "undefined" && nodeGlobal["Request"]) {
      this.global.Request = nodeGlobal["Request"] as typeof Request;
    }
    if (typeof this.global.Response === "undefined" && nodeGlobal["Response"]) {
      this.global.Response = nodeGlobal["Response"] as typeof Response;
    }
    if (typeof this.global.Headers === "undefined" && nodeGlobal["Headers"]) {
      this.global.Headers = nodeGlobal["Headers"] as typeof Headers;
    }
    if (typeof this.global.fetch === "undefined" && nodeGlobal["fetch"]) {
      this.global.fetch = nodeGlobal["fetch"] as typeof fetch;
    }
    if (typeof this.global.ReadableStream === "undefined" && nodeGlobal["ReadableStream"]) {
      this.global.ReadableStream = nodeGlobal["ReadableStream"] as typeof ReadableStream;
    }
    if (typeof this.global.TextEncoder === "undefined" && nodeGlobal["TextEncoder"]) {
      this.global.TextEncoder = nodeGlobal["TextEncoder"] as typeof TextEncoder;
    }
    if (typeof this.global.TextDecoder === "undefined" && nodeGlobal["TextDecoder"]) {
      this.global.TextDecoder = nodeGlobal["TextDecoder"] as typeof TextDecoder;
    }
    // Web Streams API — needed by MSW 2.x brotli/compression interceptors
    const streamGlobals = [
      "TransformStream",
      "WritableStream",
      "ReadableStreamDefaultReader",
      "ReadableStreamBYOBReader",
      "ByteLengthQueuingStrategy",
      "CountQueuingStrategy",
      "WritableStreamDefaultWriter",
      "WritableStreamDefaultController",
      "ReadableStreamDefaultController",
      "TransformStreamDefaultController",
    ] as const;
    for (const name of streamGlobals) {
      if (typeof this.global[name] === "undefined" && nodeGlobal[name]) {
        (this.global as Record<string, unknown>)[name] = nodeGlobal[name];
      }
    }
  }
}
