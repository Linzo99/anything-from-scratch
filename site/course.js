/**
 * Course resolver — must be loaded immediately after data.js.
 *
 * Reads ?course=<slug> from the URL, finds the matching entry in COURSES,
 * and exposes the active course's data via window globals so all existing
 * code that references PHASES / GLOSSARY / ARTIFACTS keeps working unchanged.
 *
 * Also renders the course-selector <select> in the header when more than one
 * course exists, and propagates ?course= into all internal nav/footer links.
 */
(function () {
  if (typeof COURSES === 'undefined' || !Array.isArray(COURSES) || !COURSES.length) return;

  // ── Resolve active course ────────────────────────────────────────────
  var params = new URLSearchParams(window.location.search);
  var slug   = params.get('course') || '';

  var course = null;
  for (var i = 0; i < COURSES.length; i++) {
    if (COURSES[i].slug === slug) { course = COURSES[i]; break; }
  }
  if (!course) course = COURSES[0]; // default: first course

  var isDefault = (course.slug === COURSES[0].slug);

  // ── Backward-compat globals ──────────────────────────────────────────
  window.ACTIVE_COURSE = course;
  window.PHASES        = course.phases    || [];
  window.GLOSSARY      = course.glossary  || [];
  window.ARTIFACTS     = course.artifacts || [];

  // ── URL helpers ───────────────────────────────────────────────────────
  window.addCourseParam = function (url) {
    if (isDefault) return url;
    var sep = url.indexOf('?') !== -1 ? '&' : '?';
    return url + sep + 'course=' + course.slug;
  };

  window.courseParam = function () {
    return isDefault ? '' : '?course=' + course.slug;
  };

  // ── DOM updates on DOMContentLoaded ─────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    updatePageContent();
    updateNavLinks();
    if (COURSES.length > 1) renderCourseSelector();
  });

  // ── Page content (title, masthead, etc.) ─────────────────────────────
  function updatePageContent() {
    // Always update <title>
    document.title = document.title.replace('AI Engineering from Scratch', course.title);

    // Always update course-specific GitHub links from data.json
    var _repo = course.githubRepo;
    if (_repo) {
      var _ghBtn = document.querySelector('.header-github');
      if (_ghBtn) _ghBtn.setAttribute('href', 'https://github.com/' + _repo);

      var _starsEl = document.querySelector('[data-gh-stars]');
      if (_starsEl) _starsEl.setAttribute('data-gh-stars', _repo);

      var _starBtn = document.querySelector('.masthead-btn--primary');
      if (_starBtn) {
        _starBtn.setAttribute('href', 'https://github.com/' + _repo);
        _starBtn.setAttribute('aria-label', 'Star ' + _repo + ' on GitHub');
      }

      var _starCount = document.querySelector('.masthead-btn-count');
      if (_starCount) _starCount.setAttribute('data-gh-stars', _repo);

      var _cloneEl = document.getElementById('cloneCmd');
      if (_cloneEl) _cloneEl.textContent = 'git clone https://github.com/' + _repo + '.git';
    }

    if (isDefault) return; // remaining content updates not needed for default course

    // Masthead title
    var titleEl = document.querySelector('.manual-title');
    if (titleEl) {
      var parts = course.title.split(' from ');
      if (parts.length > 1) {
        titleEl.innerHTML = escHtml(parts[0]) + '<br>from ' + escHtml(parts.slice(1).join(' from '));
      } else {
        titleEl.textContent = course.title;
      }
    }

    // Masthead tagline
    var taglineEl = document.querySelector('.manual-tagline');
    if (taglineEl) taglineEl.textContent = course.tagline;

    // Masthead attribution (hide course-specific attribution for non-default)
    var attrEl = document.querySelector('.manual-attribution');
    if (attrEl) attrEl.textContent = course.description || '';

    // TOC title
    var tocTitleEl = document.querySelector('.toc-title');
    if (tocTitleEl) {
      var totalLessons = (course.phases || []).reduce(function (a, p) { return a + p.lessons.length; }, 0);
      tocTitleEl.textContent = 'Curriculum · ' + (course.phases || []).length + ' phases · ' + totalLessons + ' lessons';
    }

    // GitHub links already updated above (runs for all courses)
  }

  // ── Propagate ?course= into internal links ───────────────────────────
  function updateNavLinks() {
    if (isDefault) return;
    var links = document.querySelectorAll(
      '.header-nav a, .footer-links a, a.logo'
    );
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute('href');
      if (!href) continue;
      // Skip external, fragment-only, and already-parameterised links
      if (href.startsWith('http') || href.startsWith('//') ||
          href.startsWith('#')    || href.startsWith('mailto')) continue;
      if (href.indexOf('course=') !== -1) continue;
      links[i].setAttribute('href', window.addCourseParam(href));
    }
    // Logo
    var logo = document.querySelector('a.logo');
    if (logo) {
      var lh = logo.getAttribute('href') || 'index.html';
      if (lh.indexOf('course=') === -1) logo.setAttribute('href', window.addCourseParam(lh));
    }
  }

  // ── Course selector <select> in header ──────────────────────────────
  function renderCourseSelector() {
    var nav = document.querySelector('.header-nav');
    if (!nav) return;

    var sel = document.createElement('select');
    sel.setAttribute('aria-label', 'Select course');
    sel.style.cssText = [
      'font-family:var(--font-mono)',
      'font-size:0.78rem',
      'letter-spacing:0.06em',
      'text-transform:uppercase',
      'background:var(--bg-surface)',
      'border:1px solid var(--rule-soft)',
      'color:var(--ink)',
      'padding:5px 10px',
      'cursor:pointer',
      'outline:none',
      'appearance:none',
      '-webkit-appearance:none',
      'border-radius:0',
      'max-width:180px',
    ].join(';');

    for (var i = 0; i < COURSES.length; i++) {
      var opt = document.createElement('option');
      opt.value = COURSES[i].slug;
      opt.textContent = COURSES[i].title.toUpperCase();
      if (COURSES[i].slug === course.slug) opt.selected = true;
      sel.appendChild(opt);
    }

    sel.addEventListener('change', function () {
      var newSlug = sel.value;
      var url = new URL(window.location.href);
      var hadLessonPath = url.searchParams.has('path');

      // Drop lesson-path and search terms — they don't transfer across courses
      url.searchParams.delete('path');
      url.searchParams.delete('q');
      if (newSlug === COURSES[0].slug) {
        url.searchParams.delete('course');
      } else {
        url.searchParams.set('course', newSlug);
      }

      // If we were on lesson.html with a path, redirect to index.html instead
      // of staying on lesson.html without a path (which shows an error).
      if (hadLessonPath) {
        url.pathname = url.pathname.replace(/[^/]*lesson\.html$/, 'index.html');
      }

      window.location.href = url.toString();
    });

    nav.insertBefore(sel, nav.firstChild);
  }

  function escHtml(str) {
    var d = document.createElement('div');
    d.textContent = str == null ? '' : String(str);
    return d.innerHTML;
  }
})();
