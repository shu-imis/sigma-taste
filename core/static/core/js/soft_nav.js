(function () {
  var runtime = window.SigmaTaste;
  if (!runtime || typeof runtime.loadScripts !== 'function') {
    return;
  }

  var ACTIVE_REQUEST = null;
  var GLOBAL_SCRIPT_SELECTOR = 'script[data-global-script][src]';
  var PAGE_SCRIPT_SELECTOR = 'script[data-page-script][src]';
  var lastKnownUrl = window.location.href;

  function isPlainPrimaryClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  }

  function isHtmlResponse(response) {
    var contentType = String(response.headers.get('content-type') || '').toLowerCase();
    return contentType.indexOf('text/html') !== -1;
  }

  function importNode(node) {
    return document.importNode ? document.importNode(node, true) : node.cloneNode(true);
  }

  function isSoftNavCandidate(link) {
    if (!link || !link.href) {
      return false;
    }
    if (link.hasAttribute('download')) {
      return false;
    }
    if (link.target && link.target !== '_self') {
      return false;
    }
    if (link.hasAttribute('data-no-soft-nav')) {
      return false;
    }

    var rawHref = String(link.getAttribute('href') || '').trim();
    if (!rawHref || rawHref.charAt(0) === '#') {
      return false;
    }

    var targetUrl = new URL(link.href, window.location.href);
    if (targetUrl.origin !== window.location.origin) {
      return false;
    }
    if (
      targetUrl.pathname === window.location.pathname &&
      targetUrl.search === window.location.search &&
      targetUrl.hash === window.location.hash
    ) {
      return false;
    }
    return true;
  }

  function isSoftFormCandidate(form) {
    if (!form) {
      return false;
    }
    var method = String(form.getAttribute('method') || 'get').toLowerCase();
    if (method !== 'get') {
      return false;
    }
    if (form.target && form.target !== '_self') {
      return false;
    }
    if (form.hasAttribute('data-no-soft-nav')) {
      return false;
    }

    var action = form.getAttribute('action') || window.location.href;
    var targetUrl = new URL(action, window.location.href);
    return targetUrl.origin === window.location.origin;
  }

  function collectGlobalScriptUrls(parsedDocument) {
    var scripts = parsedDocument.querySelectorAll(GLOBAL_SCRIPT_SELECTOR);
    var urls = [];
    for (var index = 0; index < scripts.length; index += 1) {
      urls.push(scripts[index].src);
    }
    return urls;
  }

  function collectPageScriptUrls(parsedDocument) {
    var scripts = parsedDocument.querySelectorAll(PAGE_SCRIPT_SELECTOR);
    var urls = [];
    for (var index = 0; index < scripts.length; index += 1) {
      urls.push(scripts[index].src);
    }
    return urls;
  }

  function updateCurrentHistoryState() {
    var nextState = history.state && typeof history.state === 'object' ? Object.assign({}, history.state) : {};
    nextState.__sigmaSoftNav = true;
    nextState.scrollX = window.scrollX || 0;
    nextState.scrollY = window.scrollY || 0;
    history.replaceState(nextState, '', window.location.href);
  }

  function ensureHistoryState() {
    var state = history.state;
    if (state && state.__sigmaSoftNav) {
      return;
    }
    updateCurrentHistoryState();
  }

  function resolveFormUrl(form, submitter) {
    var action = form.getAttribute('action') || window.location.href;
    var url = new URL(action, window.location.href);
    var params = new URLSearchParams();
    var formData = new window.FormData(form);

    formData.forEach(function (value, key) {
      params.append(key, value);
    });

    if (submitter && submitter.name) {
      params.append(submitter.name, submitter.value);
    }

    url.search = params.toString();
    return url.href;
  }

  function focusMainContent() {
    var main = document.querySelector('#main-content');
    if (main && typeof main.focus === 'function') {
      main.focus();
    }
  }

  function swapPage(parsedDocument, finalUrl, options) {
    var currentWrap = document.querySelector('.page-wrap');
    var nextWrap = parsedDocument.querySelector('.page-wrap');
    if (!currentWrap || !nextWrap) {
      throw new Error('Soft navigation document shape mismatch');
    }

    runtime.dispatch('sigma:before-page-swap', { url: finalUrl });
    currentWrap.replaceWith(importNode(nextWrap));

    document.title = parsedDocument.title || document.title;
    if (parsedDocument.documentElement && parsedDocument.documentElement.lang) {
      document.documentElement.lang = parsedDocument.documentElement.lang;
    }

    if (options.historyMode === 'push') {
      history.pushState(
        {
          __sigmaSoftNav: true,
          scrollX: 0,
          scrollY: 0,
        },
        '',
        finalUrl
      );
    } else {
      history.replaceState(
        {
          __sigmaSoftNav: true,
          scrollX: options.scrollX || 0,
          scrollY: options.scrollY || 0,
        },
        '',
        finalUrl
      );
    }

    runtime.runInitializers(document);

    var scrollX = options.scrollX || 0;
    var scrollY = options.scrollY || 0;
    if (options.resetScroll) {
      scrollX = 0;
      scrollY = 0;
    }
    window.scrollTo(scrollX, scrollY);
    lastKnownUrl = finalUrl;
    if (options.historyMode === 'push') {
      focusMainContent();
    }
    runtime.dispatch('sigma:page-change', { url: finalUrl });
  }

  async function navigateTo(url, options) {
    var finalUrl = String(url || '').trim();
    if (!finalUrl) {
      return;
    }

    if (ACTIVE_REQUEST && typeof ACTIVE_REQUEST.abort === 'function') {
      ACTIVE_REQUEST.abort();
    }

    var controller = 'AbortController' in window ? new AbortController() : null;
    ACTIVE_REQUEST = controller;

    try {
      var response = await window.fetch(finalUrl, {
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          Accept: 'text/html',
        },
        signal: controller ? controller.signal : undefined,
      });

      if (!response.ok || !isHtmlResponse(response)) {
        throw new Error('Soft navigation request failed');
      }

      var html = await response.text();
      var parsed = new window.DOMParser().parseFromString(html, 'text/html');
      if (!parsed.querySelector('.page-wrap')) {
        throw new Error('Soft navigation missing page shell');
      }

      var missingGlobalScripts = collectGlobalScriptUrls(parsed).filter(function (src) {
        return !runtime.isScriptLoaded(src);
      });
      if (missingGlobalScripts.length) {
        throw new Error('Soft navigation missing required global scripts');
      }

      await runtime.loadScripts(collectPageScriptUrls(parsed));

      swapPage(parsed, response.url || finalUrl, options);
    } catch (error) {
      if (error && error.name === 'AbortError') {
        return;
      }
      window.location.assign(finalUrl);
    } finally {
      if (ACTIVE_REQUEST === controller) {
        ACTIVE_REQUEST = null;
      }
    }
  }

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || !(event.target instanceof Element) || !isPlainPrimaryClick(event)) {
      return;
    }

    var link = event.target.closest('a[href]');
    if (!isSoftNavCandidate(link)) {
      return;
    }

    event.preventDefault();
    updateCurrentHistoryState();
    navigateTo(link.href, { historyMode: 'push', resetScroll: true });
  });

  document.addEventListener('submit', function (event) {
    if (event.defaultPrevented) {
      return;
    }

    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !isSoftFormCandidate(form)) {
      return;
    }

    event.preventDefault();
    updateCurrentHistoryState();
    navigateTo(resolveFormUrl(form, event.submitter), { historyMode: 'push', resetScroll: true });
  });

  window.addEventListener('popstate', function (event) {
    var state = event.state && typeof event.state === 'object' ? event.state : null;
    if (!state || !state.__sigmaSoftNav) {
      lastKnownUrl = window.location.href;
      return;
    }

    var previousUrl = new URL(lastKnownUrl, window.location.href);
    var targetUrl = new URL(window.location.href);
    lastKnownUrl = targetUrl.href;
    if (targetUrl.pathname === previousUrl.pathname && targetUrl.search === previousUrl.search) {
      return;
    }

    navigateTo(targetUrl.href, {
      historyMode: 'replace',
      scrollX: typeof state.scrollX === 'number' ? state.scrollX : 0,
      scrollY: typeof state.scrollY === 'number' ? state.scrollY : 0,
      resetScroll: false,
    });
  });

  if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
  }
  ensureHistoryState();
})();
