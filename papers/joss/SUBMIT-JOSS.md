# JOSS submission checklist — skaters

JOSS (Journal of Open Source Software) reviews the SOFTWARE, in a public GitHub
issue, against a reviewer checklist: install works, tests pass, docs and examples
exist, the paper.md states the need. The paper itself is short by design
(`papers/joss/paper.md`, ready; bibliography has DOIs wherever they exist).

## Before the form

1. Merge PR #160 so `papers/joss/paper.md` is on `main` (the branch you name at
   submission).
2. Tag a release matching `pyproject.toml` (currently 0.13.0; the last git tag is
   v0.9.1). If the PR's `gaussianize`/leaf additions warrant it, bump to 0.14.0 and
   tag that instead. JOSS asks for the version under review.
3. Optional: when the SSRN number for "Transforms All the Way Down" arrives, cite it
   in paper.md where the companion methods paper is mentioned.

## The form (joss.theoj.org, sign in with GitHub)

- Repository: `https://github.com/microprediction/skaters`
- Branch: `main`
- Version: the tag from step 2
- Suggested subject area: statistics / data science

## Notes

- The SSRN preprint is not a conflict: JOSS explicitly allows companion methods
  papers and preprints describing the same software.
- If the long JSS manuscript (`papers/skaters-jss.tex`) is ever submitted to JSS,
  disclose the JOSS paper there; the two are different manuscripts but both
  describe the package.
- Review runs as a GitHub issue on openjournals/joss-reviews; expect requests to
  run the parity suite and tests. Acceptance requires a Zenodo (or equivalent)
  archive DOI of the reviewed release at the end.
