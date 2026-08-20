(function () {
  if (window.SigmaTaste && window.SigmaTaste.__runtimeVersion) {
    return;
  }

  var initializers = [];
  var loadedScripts = Object.create(null);
  var pendingScripts = Object.create(null);

  function normalizeUrl(value) {
    var anchor = document.createElement('a');
    anchor.href = String(value || '');
    return anchor.href;
  }

  function markExistingScripts() {
    var scripts = document.querySelectorAll('script[src]');
    for (var index = 0; index < scripts.length; index += 1) {
      var script = scripts[index];
      if (script.src) {
        loadedScripts[normalizeUrl(script.src)] = true;
      }
    }
  }

  function registerInitializer(name, init) {
    if (typeof init !== 'function') {
      return;
    }

    for (var index = 0; index < initializers.length; index += 1) {
      if (initializers[index].name === name) {
        return;
      }
    }

    initializers.push({ name: name, init: init });
    init(document);
  }

  function runInitializers(root) {
    var scope = root || document;
    for (var index = 0; index < initializers.length; index += 1) {
      initializers[index].init(scope);
    }
  }

  function loadScriptOnce(src) {
    var url = normalizeUrl(src);
    if (!url || loadedScripts[url]) {
      return Promise.resolve();
    }
    if (pendingScripts[url]) {
      return pendingScripts[url];
    }

    pendingScripts[url] = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = url;
      script.async = false;
      script.onload = function () {
        loadedScripts[url] = true;
        delete pendingScripts[url];
        resolve();
      };
      script.onerror = function () {
        delete pendingScripts[url];
        reject(new Error('Failed to load script: ' + url));
      };
      document.body.appendChild(script);
    });

    return pendingScripts[url];
  }

  function loadScripts(urls) {
    var tasks = [];
    var seen = Object.create(null);

    for (var index = 0; index < urls.length; index += 1) {
      var url = normalizeUrl(urls[index]);
      if (!url || seen[url]) {
        continue;
      }
      seen[url] = true;
      tasks.push(loadScriptOnce(url));
    }

    return Promise.all(tasks);
  }

  function dispatch(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
  }

  markExistingScripts();

  window.SigmaTaste = {
    __runtimeVersion: '1',
    dispatch: dispatch,
    isScriptLoaded: function (src) {
      return !!loadedScripts[normalizeUrl(src)];
    },
    loadScripts: loadScripts,
    normalizeUrl: normalizeUrl,
    registerInitializer: registerInitializer,
    runInitializers: runInitializers,
  };
})();
