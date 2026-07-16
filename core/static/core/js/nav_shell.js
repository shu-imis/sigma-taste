(function () {
  var runtime = window.SigmaTaste;
  var mobileMq = window.matchMedia('(max-width: 1120px)');
  var listenersBound = false;

  function getNav() {
    return document.querySelector('.nav-shell');
  }

  function getNavToggle() {
    var nav = getNav();
    return nav ? nav.querySelector('[data-nav-toggle]') : null;
  }

  function isMobileViewport() {
    return mobileMq.matches;
  }

  function setMenuState(open, options) {
    var config = options || {};
    var nav = getNav();
    var navToggle = getNavToggle();
    if (!nav) {
      return;
    }

    var wasOpen = nav.classList.contains('is-open');
    nav.classList.toggle('is-open', open);
    if (navToggle) {
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (!open && wasOpen && config.focusToggle && navToggle) {
      navToggle.focus();
    }
  }

  function syncNavState() {
    var nav = getNav();
    if (!nav) {
      return;
    }
    nav.classList.toggle('is-scrolled', window.scrollY > 12);
  }

  function syncMenuByViewport() {
    if (isMobileViewport()) {
      setMenuState(false);
      return;
    }
    setMenuState(true);
  }

  function handleDocumentClick(event) {
    if (!(event.target instanceof Element)) {
      return;
    }

    var nav = getNav();
    if (!nav) {
      return;
    }

    var toggle = event.target.closest('[data-nav-toggle]');
    if (toggle && nav.contains(toggle)) {
      setMenuState(!nav.classList.contains('is-open'));
      return;
    }

    if (isMobileViewport() && nav.contains(event.target.closest('.nav-links a, .user-actions a'))) {
      setMenuState(false);
      return;
    }

    if (!isMobileViewport() || !nav.classList.contains('is-open')) {
      return;
    }
    if (event.target.closest('.nav-shell')) {
      return;
    }
    setMenuState(false);
  }

  function handleKeydown(event) {
    var nav = getNav();
    if (!nav || !isMobileViewport() || !nav.classList.contains('is-open') || event.key !== 'Escape') {
      return;
    }
    setMenuState(false, { focusToggle: true });
  }

  function bindGlobalListeners() {
    if (listenersBound) {
      return;
    }
    listenersBound = true;

    document.addEventListener('click', handleDocumentClick);
    document.addEventListener('keydown', handleKeydown);

    if (mobileMq.addEventListener) {
      mobileMq.addEventListener('change', syncMenuByViewport);
    } else if (mobileMq.addListener) {
      mobileMq.addListener(syncMenuByViewport);
    }

    window.addEventListener('scroll', syncNavState, { passive: true });
  }

  function init() {
    document.body.classList.add('js-enabled');
    bindGlobalListeners();
    syncMenuByViewport();
    syncNavState();
  }

  if (runtime && typeof runtime.registerInitializer === 'function') {
    runtime.registerInitializer('nav-shell', init);
    return;
  }

  init();
})();
