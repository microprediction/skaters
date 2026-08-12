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

# THE one nav. `benchmarks/foundation_pages.py` used to carry a second copy and
# rewrote only the inner <nav>, which is how the site ended up with three
# different menus at once (25 pages on one variant, 7 on another, and this
# constant matching neither). That generator now imports NAV from here, so this
# is the single source. Changing the menu means editing this and running the
# sweep; nothing else should write a <nav>.
CANONICAL = """  <header class="site-header">
    <div class="nav-inner">
      <a class="brand" href="/">skaters</a>
      <nav>
        <a href="/">Home</a>
        <a href="/guide.html">Methodology</a>
        <span class="menu" tabindex="0"><span class="menu-label">Usage &#9662;</span>
          <span class="drop">
            <a href="/challengers.html">Standalone</a>
            <a href="/sandwich.html">Sandwich pattern</a>
            <a href="/sidecar.html">Sidecar pattern</a>
          </span>
        </span>
        <span class="menu" tabindex="0"><span class="menu-label">Foundational &#9662;</span>
          <span class="drop">
            <a href="/foundation/chronos.html">Chronos</a>
            <a href="/foundation/tirex.html">TiRex</a>
            <a href="/foundation/timesfm.html">TimesFM</a>
            <a href="/foundation/sundial.html">Sundial</a>
            <a href="/foundation/flowstate.html">FlowState</a>
          </span>
        </span>
        <a href="/demos/">Demos</a>
        <a href="/papers.html">Papers</a>
        <a href="/performance.html">Performance</a>
        <span class="menu" tabindex="0"><span class="menu-label">Docs &#9662;</span>
          <span class="drop">
            <a href="/guide.html">Methodology</a>
            <a href="/draws.html">Draws</a>
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

# The inner <nav> only, for consumers that replace just that block.
NAV = CANONICAL[CANONICAL.index("      <nav>"):CANONICAL.index("</nav>") + len("</nav>")]

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
