# Error taxonomy — full reference

This is the long form of the error taxonomy summarised in the main
SKILL.md. Read this file before running the first audit on any new
project. Every error class includes:

- **Diagnostic pattern** — how the agent recognises this class without
  native fluency.
- **Bucket assignment** — Likely error vs Worth checking, and the
  conditions that flip a class from one to the other.
- **Worked examples** — sanitised illustrations of the pattern in the
  wild.
- **Pitfalls** — common mistakes when applying the class.

The taxonomy is organised into two top-level buckets: **Likely errors**
(things even a non-native reviewer can defend) and **Worth checking**
(things that need a native judgment call). Within each bucket, classes
are ordered roughly by how often they show up in practice.

Load triggers: before the first audit on a new project; classifying a finding's error class or bucket

---

## Likely errors

### 1. Placeholder text on metas

**Diagnostic pattern.** The meta description is one of:

- the page title repeated verbatim,
- a generic phrase ("Disclaimer", "General terms", "Privacy policy"),
- the page title plus a brand-name suffix ("Customer Service - Brand
  Name"),
- a one-word category label.

**Bucket.** Always Likely error. The intent of a meta description is to
summarise the page; a copy of the page title fails that intent
unambiguously.

**Worked example.**

> Field: meta_description
> Excerpt: "Privacy Policy - BrandName"
> Diagnosis: The meta description is the page title repeated. It should
> summarise what the privacy policy covers.

**Pitfall.** Some sites genuinely use the page title as their meta
description for category pages (e.g., short category names where the
SEO value is the title itself). Don't flag if the meta description is
the title *plus* a meaningful suffix that adds context.

---

### 2. Body excerpt in meta description

**Diagnostic pattern.** The meta description reads as a sentence pulled
from the middle of the article body — references "the methods above" or
"as we discussed", starts with "However" or "But", ends mid-clause, or
otherwise depends on context not present in the description.

**Bucket.** Always Likely error.

**Worked example.**

> Field: meta_description
> Excerpt: "We're now a few days to a week in, and thanks to one of
> the techniques above, the results have been excellent."
> Diagnosis: This reads as a body excerpt — references "the techniques
> above" with no techniques visible. Needs to be replaced with a
> proper one-sentence summary of the page.

**Pitfall.** Some sites deliberately use sentence-fragment metas as
hooks. If the meta description is grammatically complete and reads as
intentional, flag it as Worth checking, not Likely error.

---

### 3. Grammar agreement violations

**Diagnostic pattern.** Visible mismatch in gender, number, or case
between an article, adjective, or pronoun and the noun it modifies.

**Bucket.** Likely error when the mismatch is unambiguous from the
surface text. Worth checking when the rule depends on context the
non-native reviewer can't see (e.g., antecedents in earlier paragraphs).

**Worked example.**

> Field: meta_description
> Excerpt: "Las selección de productos..."
> Diagnosis: Gender disagreement. "Selección" is feminine singular; the
> article should be "La", not "Las".

**Pitfall.** Some agreement rules vary by register or dialect (e.g.,
European vs Brazilian Portuguese). Hedge if you can't tell which
variant the site targets.

---

### 4. Missing or wrong diacritics

**Diagnostic pattern.** A letter that the language's orthography
requires to carry a diacritic appears without it, or with the wrong
one (acute where the language uses grave, etc.).

**Bucket.** Likely error when the same word elsewhere on the site is
written with the correct diacritic. Worth checking when the diacritic
is missing systematically across the site — could indicate a font or
encoding issue rather than a translator error.

**Worked example.**

> Field: h1
> Excerpt: "Como elegir el producto perfecto"
> Diagnosis: Interrogative — should be "Cómo" with an acute accent.
> Other pages on the site use the correct form.

**Pitfall.** Some URL slugs are intentionally ASCII (no diacritics) for
compatibility; don't flag diacritic absence in URLs unless the user
explicitly wants slug review.

---

### 5. Typos

**Diagnostic pattern.** A word that doesn't match the language's
spelling, often a transposed or doubled character. Verifiable by
cross-comparison with the same word elsewhere on the site or by
running through a standard spell-checker for the target language.

**Bucket.** Likely error when the misspelling is clearly unintentional
(single character off from the correct form, no plausible reading as a
real word).

**Worked example.**

> Field: meta_description
> Excerpt: "...una barreja índica dominante que no decepciona. És molt
> fort,i prefereix entorns de cultiu cálids per produir els milors
> resultats."
> Diagnosis: "milors" is a typo for "millors"; "fort,i" is missing a
> space after the comma.

**Pitfall.** Don't flag deliberate informal spellings (slang, brand
voice) as typos. If the same form appears repeatedly across the site,
treat it as Worth checking, not Likely error.

---

### 6. Cross-language contamination

**Diagnostic pattern.** A word or phrase from a different language
appearing in the target text — often Spanish words in Catalan,
English words in non-English markets, or vice versa.

**Bucket.** Likely error when the contaminating word has a clear
target-language equivalent that the site uses elsewhere. Worth
checking when the contaminating word is a recognised loanword or
intentional brand-name retention.

**Worked example.**

> Field: meta_description
> Excerpt: "...una barreja de cafè i te y altres productes..."
> Diagnosis: "y" is Spanish; Catalan uses "i". Other Catalan pages on
> the site use "i" consistently.

**Pitfall.** Brand names and product names are often intentionally
left in the source language. Don't flag those.

---

### 7. Untranslated source-language text

**Diagnostic pattern.** A string on a localised page that's still in
the source language (most commonly English), where every comparable
page on the site is translated. Often appears on legal pages, customer
service pages, or footer text.

**Bucket.** Likely error.

**Worked example.**

> Field: meta_description
> Excerpt: "Privacy Policy - BrandName"
> Diagnosis: English-language placeholder on a [target language] page.
> Other localised pages have their meta descriptions translated.

**Pitfall.** Some technical strings are intentionally left in English
across markets (product codes, brand names). Flag only when the string
is the kind of text that would normally be translated.

---

### 8. Encoded HTML entities in visible text

**Diagnostic pattern.** Literal entity references (`&amp;`, `&#039;`,
`&nbsp;`) appearing in the rendered text rather than being decoded
into the characters they represent.

**Bucket.** Likely error. Always a templating bug, never deliberate.

**Worked example.**

> Field: meta_description
> Excerpt: "...home &amp; garden essentials..."
> Diagnosis: HTML entity not decoded. Should render as "home &
> garden essentials".

**Pitfall.** None — this is a clean class.

---

### 9. Truncated or broken sentences

**Diagnostic pattern.** Text ending mid-clause, double negation,
missing sentence break between two sentences, or punctuation that's
syntactically impossible (stray comma between subject and verb).

**Bucket.** Likely error when the break is clearly a mechanical
failure (truncation at a character limit, missing space after
punctuation). Worth checking when the structure is unusual but could
be a deliberate stylistic choice.

**Worked example.**

> Field: meta_description
> Excerpt: "...Mais quelle est la meilleure approche pour faire pousser
> sans problèmes ces"
> Diagnosis: Sentence cut off after "ces". Likely truncation at a
> character limit.

**Pitfall.** Some marketing copy uses intentional sentence fragments.
Don't flag short fragments unless they're clearly truncations.

---

### 10. Content mismatch with source

**Diagnostic pattern.** The target-language page makes a different
factual claim from the source-language page. The agent can detect this
only by comparing the two side by side.

**Bucket.** Likely error when the mismatch is clear and substantive
(different number, different actor, different claim). Worth checking
when the divergence could be a deliberate localisation choice
(removing a claim that doesn't apply in the target market).

**Worked example.**

> Field: meta_description
> Source (en): "BrandName is one of the fastest-growing manufacturers
> of small kitchen appliances in Europe."
> Target (es): "BrandName se encuentra entre los principales fabricantes
> de electrodomésticos de cocina de crecimiento rápido de Europa."
> Diagnosis: The English describes the company as fast-growing; the
> Spanish describes the products as fast-growing. Looks like a
> misreading of "fastest-growing manufacturer" → "manufacturer of
> fast-growing products".

**Pitfall.** Deliberate market-specific adaptations look like
mismatches but are intentional. Always hedge if the divergence could
be regulatory ("we don't make this claim in markets where it's
restricted").

---

### 11. Title / H1 inconsistency on the same page

**Diagnostic pattern.** The `<title>` and the `<h1>` on a single URL
use different wording, spelling, or casing for what should be the same
page label.

**Bucket.** Likely error when the inconsistency is in spelling,
diacritics, or capitalisation. Worth checking when the title and H1
intentionally serve different audiences (SEO-optimised title vs
human-readable H1).

**Worked example.**

> URL: example.com/cz/kuchynske-spotrebice
> Title: "Kuchyňské Spotřebiče - BrandName"
> H1: "Kuchynske Spotrebice"
> Diagnosis: H1 missing diacritics on every word; title has them
> correctly.

**Pitfall.** Some platforms add a brand-name suffix to the title that
isn't in the H1. Don't flag that as inconsistency — it's a deliberate
template.

---

### 12. Missing meta description

**Diagnostic pattern.** The page has no `<meta name="description">`
tag at all, or the tag is present but empty.

**Bucket.** Likely error.

**Worked example.**

> Field: meta_description
> Excerpt: (no meta description tag)
> Diagnosis: The page has no meta description. Needs one.

**Pitfall.** None — this is a clean class.

---

## Worth checking

### 13. Register or formality

**Diagnostic pattern.** A page uses formal address (e.g., "vous" in
French, "Sie" in German, "voi" in Italian) where comparable pages on
the same site use informal ("tu", "du", "tu"), or vice versa.

**Bucket.** Always Worth checking. Register choice is a legitimate
translator decision, but cross-page inconsistency is worth flagging.

**Worked example.**

> Field: meta_description
> Excerpt: "Vi presentiamo il nostro nuovo modello: potreste trovare
> molti dettagli che vi piaceranno..."
> Diagnosis: Switches to formal "voi" form; most other product pages
> on the site use "tu". Could be intentional for this page, but is
> inconsistent with the rest of the catalogue.

**Pitfall.** Some sites deliberately use different registers for
different sections (formal for legal pages, informal for product
pages). Check the section context before flagging.

---

### 14. Idiom literalness

**Diagnostic pattern.** A target-language sentence reads as a literal
word-by-word rendering of a source-language idiom, where the natural
target-language equivalent would phrase it differently.

**Bucket.** Always Worth checking. Literal renderings can be
deliberate stylistic choices.

**Worked example.**

> Field: meta_description
> Excerpt: "Hon är tungt träffande och föredrar varmt växande miljöer
> för bästa resultat."
> Diagnosis: "tungt träffande" is a literal calque of English
> "heavy-hitting". Reads awkwardly in Swedish; the natural phrasing
> would be "Den slår hårt" or "Den har en kraftfull effekt".

**Pitfall.** Some idioms travel naturally between languages — don't
flag those.

---

### 15. Anglicism choice

**Diagnostic pattern.** An English word or phrase appears in the
target-language text where a local equivalent exists. Common in
marketing copy and technical terminology.

**Bucket.** Always Worth checking. Anglicism use is a register
decision.

**Worked example.**

> Field: meta_description
> Excerpt: "Title, H1, and meta description all use the English phrase
> 'New Season Collection'..."
> Diagnosis: Could be an intentional anglicism (some industries
> routinely use English category terms in NL/BE), but worth confirming.

**Pitfall.** Some industries (tech, fashion, fitness, lifestyle)
routinely use English loanwords across all markets. Don't flag those
unless the same site uses the local equivalent elsewhere.

---

### 16. Brand voice consistency

**Diagnostic pattern.** Tone shifts between pages within the same site
section — formal vs casual, marketing vs neutral, technical vs
plain-language.

**Bucket.** Always Worth checking.

**Worked example.**

> Field: body
> Excerpt: (long body passage)
> Diagnosis: This product page describes the appliance in clinical,
> technical-spec language ("certified industrial-grade construction").
> Other product pages on the site use marketing-tone language
> ("excellent results, premium quality"). Worth a review of whether the
> technical framing fits the brand voice.

**Pitfall.** Some brands deliberately use different voices for
different categories. Check that the inconsistency isn't structural.

---

### 17. Title case vs sentence case

**Diagnostic pattern.** Capitalisation conventions that differ from
the target language's norms — for example, English-style title case
in a language that uses sentence case.

**Bucket.** Likely error when the capitalisation is clearly wrong for
the language (e.g., capitalising every word of a French sentence in
running text). Worth checking when the capitalisation could be a
deliberate stylistic choice (button labels, headlines).

**Worked example.**

> Field: meta_description
> Excerpt: "Entrez Vos Préférences Dans Notre Outil Et Trouvez Le
> Produit Idéal en Toute Simplicité"
> Diagnosis: Rendered in title case; French convention is sentence
> case. Worth confirming whether this is a deliberate styling choice
> or a default from an English template.

**Pitfall.** Don't flag headlines or H1s for title case — that's
sometimes a brand styling decision.

---

### 18. Cultural adaptation

**Diagnostic pattern.** A reference, idiom, or example in the target
text that may not carry the same meaning in the target market.

**Bucket.** Always Worth checking.

**Pitfall.** Cultural adaptation is the most subjective class.
Default to hedging strongly — even more than the rest of the Worth
checking bucket.

---

## Applying the taxonomy

When the agent works through an audit, it should run each URL through
all 18 classes (12 Likely error classes + 6 Worth checking classes) in
order, and record every finding that matches. Multiple findings on the
same URL are normal — a page with placeholder text *and* a typo
generates two findings, one per class.

If the page has zero findings after the full pass, record that —
"no issues flagged in this batch" is a useful signal in itself, both
for the verification step later and for tracking site quality over
time.

### When a finding could fit two classes

When a finding could fit two classes (e.g., a typo that's also a
cross-language contamination), pick the class that gives the clearest
diagnosis to the native reviewer. The goal is actionability, not
taxonomic purity. If unsure, the agent can record the finding once
with a diagnosis that names both — e.g., "Spanish word 'y' instead of
Catalan 'i' — cross-language contamination and a spelling issue
combined".

### When the source-language page is also broken

Sometimes the source-language page itself has an error that's been
faithfully reproduced in the translation. In that case, flag the
finding on every affected language *including the source* — the audit
isn't about the translations alone, it's about the deployed content
quality across all versions.

---

## Extending the taxonomy

This taxonomy grows by encountering new failure modes. When you find a
pattern that doesn't fit any of the 18 classes above:

1. Add a section to this file under the appropriate bucket.
2. Include the diagnostic pattern, bucket assignment, a worked
   example, and pitfalls.
3. Reference the new class from the main SKILL.md summary.
4. If you're maintaining a fork, open a pull request on the upstream
   repo so other users benefit from the new class.

The taxonomy is the load-bearing methodology of the skill — the more
real-world examples it covers, the more reliably non-native reviewers
can contribute to translation quality work.
