# Cell Learning

A [Quarto](https://quarto.org) website built from a Notion export of the
*Cell Learning* research proposal.

## Structure

```
index.qmd            Main proposal (was "Cell Learning ….md")
people/              People pages
  index.qmd          List of people
  *.qmd              One page per person (with a "Related references" table)
references/          Reference library
  index.qmd          Sortable table of all 57 references → detail pages + PDFs
  *.qmd              One page per reference (metadata + BibTeX + PDF link)
files/               All PDFs (the "included files" folder)
images/              Figures (PNG)
styles.css           Site styling
_quarto.yml          Quarto website config (nav, theme, render list)
_convert.py          One-shot converter (Notion export → .qmd). Re-runnable.
_notion_source/      Original Notion export, kept as a backup.
                     Ignored by Quarto (the leading "_"). PDFs/PNGs were moved
                     out of it into files/ and images/.
_site/               Rendered HTML output (generated; safe to delete).
```

## Build / preview

```bash
quarto preview      # live local server with auto-reload
quarto render       # build the static site into _site/
```

## Regenerating from the Notion source

`_convert.py` rebuilds all `.qmd` pages from `_notion_source/`:

```bash
python3 _convert.py && quarto render
```

It rewrites Notion's internal links to Quarto page links, points citation
links at the per-paper reference pages, and points PDF/image links at
`files/` and `images/`. Hand-edits to the generated `.qmd` files will be
overwritten if you re-run it.

## Notes on the conversion

- Notion "self-links" (a link whose target was the page itself) were flattened
  to plain text.
- Two `<aside>` callouts in the proposal became Quarto `callout-note` blocks.
- BibTeX case-protection braces (e.g. `{MSH3}`) were stripped from display
  titles but kept inside the BibTeX blocks.
- A Notion export glitch had dumped the *entire* reference database into a few
  people's "related references" tables (57 rows); those dumps were dropped.
