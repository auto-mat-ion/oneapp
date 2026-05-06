/* eslint-disable */
(function () {
  'use strict';

  const XHR = window.XMLHttpRequest.prototype;
  const originalXHROpen = XHR.open;
  const originalXHRSend = XHR.send;

  XHR.open = function (method, url) {
    this._method = method;
    this._url = url;
    this._startTime = Date.now();
    return originalXHROpen.apply(this, arguments);
  };

  XHR.send = function (postData) {
    const url = this._url;
    const method = this._method;
    const startTime = this._startTime;

    this.addEventListener('load', function () {
      const endTime = Date.now();
      const duration = endTime - startTime;
      const status = this.status;
      try {
        const responseText = this.responseText;

        window.postMessage(
          {
            type: 'networkRequest',
            protocol: 'xhr',
            method: method,
            url: url,
            status: status,
            duration: duration,
            response: responseText,
            timestamp: endTime
          },
          '*'
        );
      } catch (error) {
        window.postMessage(
          {
            type: 'networkRequest',
            protocol: 'xhr',
            method: method,
            url: url,
            status: status,
            duration: duration,
            response: '[unavailable]',
            timestamp: endTime
          },
          '*'
        );
      }
    });

    this.addEventListener('error', function () {
      window.postMessage(
        {
          type: 'networkRequest',
          protocol: 'xhr',
          method: method,
          url: url,
          status: 0,
          error: true,
          timestamp: Date.now()
        },
        '*'
      );
    });

    return originalXHRSend.apply(this, arguments);
  };

  const originalFetch = window.fetch;

  window.fetch = async function (...args) {
    const url = args[0]?.toString() || '';
    const startTime = Date.now();
    let method = 'GET';

    if (args[1] && typeof args[1] === 'object') {
      method = args[1].method || 'GET';
    }

    try {
      const response = await originalFetch.apply(this, args);
      const endTime = Date.now();
      const duration = endTime - startTime;

      response
        .clone()
        .text()
        .then((responseText) => {
          window.postMessage(
            {
              type: 'networkRequest',
              protocol: 'fetch',
              method: method,
              url: url,
              status: response.status,
              duration: duration,
              response: responseText,
              timestamp: endTime
            },
            '*'
          );
        })
        .catch(() => {
          // Silently handle clone errors
        });

      return response;
    } catch (error) {
      window.postMessage(
        {
          type: 'networkRequest',
          protocol: 'fetch',
          method: method,
          url: url,
          status: 0,
          error: true,
          errorMessage: error.message,
          timestamp: Date.now()
        },
        '*'
      );
      throw error;
    }
  };
})();
