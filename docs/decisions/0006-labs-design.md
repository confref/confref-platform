# 0006 The design of the labs: the project site's, set apart, everything in beta

Status: accepted · Date: 2026-11-09

## Context

Kai asked for the labs to fit the design of www.confref.org, with all services declared beta, and visibly different
so that users do not confuse labs and www in the navigation (2026-11-09).

## Decision

- **The same stylesheet** as www.confref.org (copied into the kit, `site/kit-src/www.css`), fonts, colours and
  components, plus the labs additions (`site/kit-src/labs.css`).
- **Set apart:** a striped red beta line above the header on every page ("services in development", with the link to
  www.confref.org); a dark header with the "labs" mark beside the wordmark; the link to www.confref.org at the end of
  the navigation as an outlined button with an arrow; a dark rule above the footer.
- **Beta everywhere:** a beta badge on every service, page head and card, and a beta note on the landing pages.
- **The kit:** `/kit/1/header.html`, `/kit/1/footer.html`, `/kit/1/confref.css`, built by the labs site and put into
  the pages of the application and of the showcases by nginx (SSI). Kit 1 only gets compatible changes.

## Consequences

www.confref.org links to the labs from its navigation with the same "labs" mark, so that the change of site is seen
before the click.
