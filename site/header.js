/**
 * Shared header behaviors: live GitHub star counter.
 * Reads the repo from [data-gh-stars] (set by course.js) or ACTIVE_COURSE.
 */
(function () {
  var CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

  function getRepo() {
    var el = document.querySelector('[data-gh-stars]');
    if (el) {
      var r = el.getAttribute('data-gh-stars');
      if (r) return r;
    }
    if (window.ACTIVE_COURSE && window.ACTIVE_COURSE.githubRepo) return window.ACTIVE_COURSE.githubRepo;
    return null;
  }

  function format(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
  }

  function paint(repo, n) {
    var els = document.querySelectorAll(
      '.header-github .star-count, #starCount, [data-gh-stars="' + repo + '"]'
    );
    for (var i = 0; i < els.length; i++) {
      els[i].textContent = format(n);
      els[i].removeAttribute('data-loading');
    }
  }

  function load() {
    var repo = getRepo();
    if (!repo) return;

    var CACHE_KEY = 'gh:stars:' + repo;

    function readCache() {
      try {
        var raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        var parsed = JSON.parse(raw);
        if (Date.now() - parsed.t > CACHE_TTL_MS) return null;
        return parsed.n;
      } catch (e) {
        return null;
      }
    }

    function writeCache(n) {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ n: n, t: Date.now() }));
      } catch (e) {}
    }

    var cached = readCache();
    if (cached != null) {
      paint(repo, cached);
      return;
    }

    fetch('https://api.github.com/repos/' + repo, {
      headers: { Accept: 'application/vnd.github+json' },
    })
      .then(function (r) {
        if (!r.ok) throw new Error('gh ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var n = data.stargazers_count;
        if (typeof n !== 'number') return;
        writeCache(n);
        paint(repo, n);
      })
      .catch(function () {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
