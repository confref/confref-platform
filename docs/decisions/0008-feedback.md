# 0008 Feedback on the data

Status: accepted · Date: 2026-11-09 · Builds on confref-data decision 0022

## Context

Visitors of the landing pages and the labs see errors in the data: records grouped into the wrong series or event,
two identifiers for one event, a wrong fact of a source. Most single facts come from sources that can be corrected
where they are kept (ConfIDent, Wikidata, dblp, the GND); errors of the linking and clustering are confref's own.

## Decision

- **A Feedback button in the labs header** (`/kit/1/header.html`), so every page that includes the header (SSI) has
  it, the landing pages and the showcases included, without changes of their own. The script `/kit/1/feedback.js`
  and the styles `/kit/1/feedback.css` come with the header; any element with `data-cr-feedback` opens the panel.
- **Two steps:** the panel first says where feedback goes: any feedback is welcome as an issue on confref-data, above
  all on the linking of records and their grouping into series and events; an error in a record of a source is best
  also corrected at the source (the ways to report to each source are on www.confref.org/feedback/); missing
  conferences are added to ConfIDent, not to confref (confref-data 0022). Then a form: the resource it is about,
  the selected text (taken from what the visitor selects while the panel is open), the feedback, the subject, the
  page.
- **The resource** is found on the page: the element with `data-cr-iri` around the selected text (the records of a
  landing page, the events of a series); else `<meta name="cr:subject">`; else the `?iri=` of the address; else the
  canonical link or the path of the page (`/series/…`, `/event/…`, `/data/…`, `/datasets/…`, `/ontology/…`).
- **The issue** goes to the public tracker of confref-data on GitHub, through the issue form
  `.github/ISSUE_TEMPLATE/feedback.yml` there (label `feedback`, fields `iri`, `page`, `quote`, `description`),
  its fields filled by the link.
- **Without a GitHub account:** the whole text (subject and body) can be copied, to send it to the contact of the
  project (the legal notice of www.confref.org) or to keep it. No e-mail address in the panel.
- **Nothing is sent by the platform:** the script builds a link and a text; the visitor submits the issue on GitHub.
  The draft is kept in the browser's session storage for the page, so that closing the panel loses nothing. No form
  on the platform takes input ([0001](0001-platform.md): read-only).
