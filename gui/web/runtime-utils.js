(function (global) {
  const managedIntervals = [];
  const managedTimeouts = [];

  function throttle(func, limit) {
    let inThrottle = false;
    return function throttled(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => {
          inThrottle = false;
        }, limit);
      }
    };
  }

  class EventManager {
    constructor() {
      this.listeners = [];
    }

    addListener(element, event, handler, options) {
      if (!element || typeof element.addEventListener !== "function") {
        return;
      }
      element.addEventListener(event, handler, options);
      this.listeners.push({ element, event, handler, options });
    }

    removeAllListeners() {
      this.listeners.forEach(({ element, event, handler, options }) => {
        try {
          element.removeEventListener(event, handler, options);
        } catch (_error) {
        }
      });
      this.listeners = [];
    }
  }

  const registerInterval = (fn, ms) => {
    const id = setInterval(fn, ms);
    managedIntervals.push(id);
    return id;
  };

  const registerTimeout = (fn, ms) => {
    const id = setTimeout(fn, ms);
    managedTimeouts.push(id);
    return id;
  };

  const clearManagedTimers = () => {
    managedIntervals.forEach((id) => clearInterval(id));
    managedTimeouts.forEach((id) => clearTimeout(id));
  };

  global.JarvisRuntimeUtils = {
    EventManager,
    throttle,
    registerInterval,
    registerTimeout,
    clearManagedTimers,
    managedIntervals,
    managedTimeouts,
  };
})(window);
