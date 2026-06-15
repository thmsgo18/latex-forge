## Writing an excellent document

This section is the quality bar for the **content you write**. A finished document
should read like the work of a careful human expert — a clear thesis, an argument
that builds section by section, every claim earned. Producing a file that merely
*compiles* is not the goal; producing one that would earn a top grade or pass peer
review is.

### Start from the source material

A report documents real work — it is not written from imagination. Before writing,
establish what it is about:

- **If the user points you to a project** (a code repository, a dataset, notes, an
  existing draft, a folder), read it thoroughly first. Every factual claim, code
  excerpt, architecture description, figure and result must come from what is
  actually there.
- **If you are writing in-place** inside an existing project, that surrounding
  project *is* the source — inspect it the same way.

Ground the whole report in that material. Where a needed figure, measurement or
result isn't available there, mark it with a `% TODO` (see below) rather than
inventing it.

### What "done" means

Do not stop at a skeleton, and never leave the template's guidance comments
(`% Présentez...`, `% List the objectives...`) or placeholder text in the final
document. Replace every one of them with real, substantive prose. The reader should
never see scaffolding.

### Principles

- **One clear thesis, one throughline.** The document answers a specific question or
  defends a specific position. Every section visibly advances it; the reader always
  knows why they are reading the current paragraph.
- **Evidence over assertion.** Back every non-obvious claim with a citation, a
  figure/table, data, or explicit reasoning. Clearly separate established facts
  (which you cite) from your own contribution (which you demonstrate). Never assert
  something the reader has no reason to believe.
- **Structure and signposting.** The introduction frames context → problem →
  objectives → outline. Each section opens by stating its purpose and ends with a
  sentence that bridges to the next. The conclusion answers the question raised in
  the introduction, then states limitations and future work — it does not merely
  summarize.
- **Depth and specificity.** Prefer concrete, specific statements over generic ones;
  explain *why* and *how*, not only *what*. Cut filler, truisms, and sentences that
  would be true of any project.
- **Right length, not maximum length.** Match length to substance. A precise, concise
  report beats a padded one — never inflate with repetition, restated obviousness, or
  boilerplate just to look thorough.
- **Varied, well-paced layout.** Avoid walls of prose. Break content up with bullet
  and numbered lists, tables, figures and diagrams, equations, and quoted sources
  wherever they carry the idea better than a paragraph — with prose as the connective
  tissue between them.
- **Critical stance.** Discuss trade-offs, alternatives you considered and rejected,
  and the limits of your results. An honest account of what did *not* work is worth
  more than an unbroken success story.
- **Register and clarity.** Formal, neutral, precise. Define every term and expand
  every acronym on first use. One idea per paragraph. Be direct; avoid hedging and
  padding. Keep terminology and notation consistent throughout.
- **Coherence.** Cross-reference every figure, table, and section (`\ref`/`\cref`)
  and make sure each one is actually discussed in the prose — never drop in a figure
  without commentary. Keep tense and notation uniform from start to finish.

### Content you don't have yet

Write the full document anyway: complete the structure, the argumentation, and the
surrounding prose everywhere. Where a *specific* number, measurement, result, or
factual claim would need real data or a real source you don't have, write the
analysis around it and insert a clearly-marked placeholder for the missing datum —
`% TODO: replace with actual <result> from <where to find it>` — instead of
inventing a plausible-looking value (see *Reported data and metrics* below). This
keeps the document honest and almost finished: only the real specifics remain to be
dropped in.

### Before you finish — self-review

Re-read the compiled PDF (not just the source) and check each point:

- [ ] Each section delivers on what the introduction promised.
- [ ] Every non-trivial claim is supported (citation, figure, data, or reasoning) and
      traces back to the source material.
- [ ] No generic filler, no padding, no leftover template comments or placeholder text.
- [ ] Content is varied (prose, lists, tables, figures, formulas) — not a wall of text.
- [ ] Every figure and table is referenced *and* discussed in the prose.
- [ ] Acronyms and key terms are defined once; terminology is consistent.
- [ ] Any remaining `% TODO` factual gaps are collected and surfaced to the user.
- [ ] All content is written in the document's language (see below).
- [ ] Layout holds on the PDF: nothing in the margins, tables sized correctly,
      diagrams free of overlaps, table of contents on one page (see *Content
      guidelines* below).

---
