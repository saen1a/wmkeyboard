---
name: wmk-docs
description: Write or repair a WM Keyboard documentation page. Use for anything under docs/, a README section, or a settings link that CI validates.
---

# WM Keyboard docs

## Read first

- `docs/CONTENT_GUIDE.md` is the contract. Read it before editing a page.
- `docs/package.json` holds the scripts; `docs/astro.config.mjs` holds the
  Starlight configuration and the link validator.

## Commands

```sh
cd docs
npm ci
npm run check
```

`npm run check` is `CHECK_LINKS=1 astro build`: a broken internal link fails
the build instead of shipping to Pages. CI runs the same command.

## Content rules

- Never invent behaviour. Every claim is verified against `app/`, `core/`, or
  `feature/`, or observed on a device for a hard case.
- One page, one job. Split and cross-link instead of nesting H4s.
- Keep the frontmatter `description`; it feeds search, SEO, and link cards.
  Quote it, because an unquoted colon breaks the build.
- Link with absolute paths and a trailing slash: `/typing/gestures/`.
- American-neutral English, second person, present tense.
- A stub is unfinished. Mark it with `:::caution[Draft page]` and remove the
  marker when the page is done.
- Privacy claims are specific: name what is sent, to whom, and when. Never
  write "we care about your privacy".

## Traps

- The docs site is a separate npm project. A Gradle green build says nothing
  about a broken link.
- Screenshot imports are staged under `docs/screenshots/.incoming/`, which is
  ignored. Do not commit the staging directory.
- The content guide is descriptive, not a suggestion. A page that breaks it is
  a review finding even when the build passes.

## Done means

- `npm run check` exits 0 from `docs/`.
- Every new factual claim names the code path that proves it.
- New links resolve, and a moved page updates the pages that link to it.
