"use strict";

// Minimal CJS stub of rettime for Jest (Node.js / jsdom) environments.
// rettime is ESM-only; MSW 2.x uses it for network-event forwarding which is
// not exercised in unit tests.

// TypedEvent extends MessageEvent; Node 18+ and jsdom both provide MessageEvent.
// Fall back to a plain Event subclass if MessageEvent is not available.
const BaseEvent = typeof MessageEvent !== "undefined" ? MessageEvent : Event;
class TypedEvent extends BaseEvent {
  constructor(type, init) {
    super(type, init);
  }
}

class Emitter {
  constructor() {
    this._listeners = new Map();
    this._wildcardListeners = [];
    this.hooks = {
      on: () => {},
      removeListener: () => {},
    };
  }

  on(type, listener) {
    if (type === "*") {
      this._wildcardListeners.push(listener);
    } else {
      if (!this._listeners.has(type)) this._listeners.set(type, []);
      this._listeners.get(type).push(listener);
    }
    return this;
  }

  off(type, listener) {
    if (type === "*") {
      const idx = this._wildcardListeners.indexOf(listener);
      if (idx !== -1) this._wildcardListeners.splice(idx, 1);
    } else {
      const arr = this._listeners.get(type);
      if (arr) {
        const idx = arr.indexOf(listener);
        if (idx !== -1) arr.splice(idx, 1);
      }
    }
    return this;
  }

  emit(event) {
    const eventType = event && event.type ? event.type : event;
    const listeners = this._listeners.get(eventType) || [];
    const wildcard = [...this._wildcardListeners];
    for (const fn of [...listeners]) fn(event);
    for (const fn of wildcard) fn(event);
  }

  removeAllListeners(type) {
    if (type) {
      this._listeners.delete(type);
    } else {
      this._listeners.clear();
      this._wildcardListeners = [];
    }
    return this;
  }
}

module.exports = { Emitter, TypedEvent };
