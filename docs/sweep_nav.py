"""Single source of truth for the site header/navigation.

CANONICAL below is the one authoritative header. This script stamps it into
every docs/**/*.html (top-level AND subdirectories like demos/ and challengers/),
replacing the existing <header class="site-header">...</header> block. It is
idempotent and recursive, so the nav can never drift again: change CANONICAL,
run the sweep, done. Absolute hrefs (/, /challengers.html, ...) mean the same
block works verbatim at any directory depth.

    python docs/sweep_nav.py          # rewrite every page from CANONICAL
    python docs/sweep_nav.py --check  # audit only; exit 1 if any page differs
"""
import glob
import os
import re
import sys

CANONICAL = """  <header class="site-header">
    <div class="nav-inner">
      <a class="brand" href="/">skaters</a>
      <nav>
        <a href="/">Home</a>
        <span class="menu" tabindex="0"><span class="menu-label">Results &#9662;</span>
          <span class="drop">
            <a href="/challengers.html">Direct comparisons</a>
            <a href="/sandwich.html">Collaborative use</a>
          </span>
        </span>
        <a href="/demos/">Demos</a>
        <a href="/guide.html">Guide</a>
        <a href="/papers.html">Papers</a>
        <span class="menu" tabindex="0"><span class="menu-label">Docs &#9662;</span>
          <span class="drop">
            <a href="/scope.html">Scope</a>
            <a href="/languages.html">Languages</a>
            <a href="/heritage.html">Heritage</a>
            <a href="/faq.html">FAQ</a>
            <a href="/skills.html">Skills</a>
          </span>
        </span>
        <a href="https://github.com/microprediction/skaters">GitHub</a>
      </nav>
    </div>
  </header>"""

HEADER_RE = re.compile(r'[ \t]*<header class="site-header">.*?</header>', re.DOTALL)


def main():
    check = "--check" in sys.argv
    root = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(root, "**", "*.html"), recursive=True))
    drift, missing = [], []
    for f in files:
        s = open(f).read()
        if not HEADER_RE.search(s):
            missing.append(os.path.relpath(f, root))
            continue
        new = HEADER_RE.sub(lambda _m: CANONICAL, s, count=1)
        if new != s:
            drift.append(os.path.relpath(f, root))
            if not check:
                open(f, "w").write(new)
    if missing:
        print("no site-header (skipped): " + ", ".join(missing))
    if check:
        if drift:
            print("NAV OUT OF SYNC:\n  " + "\n  ".join(drift))
            return 1
        print(f"nav in sync across {len(files) - len(missing)} pages")
        return 0
    print("swept:\n  " + "\n  ".join(drift) if drift else "all pages already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
