# AI Tells

Markers that flag prose as machine-generated, with the rewrite move for each.
No single tell proves anything — humans wrote the training data — but tells
cluster; three or more in one passage is a rewrite signal
(<https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing>).
Rewrite the fact densely; delete only when the sentence carries no fact.

## Rhetorical-structure tells

| Tell | Looks like | Fix |
|---|---|---|
| Negation pivot | "It's not X, it's Y", "This isn't just X — it's Y" | State what the thing is; cut the strawman |
| Staccato negative parallel | "No X. No Y. Just Z." | One plain sentence naming Z |
| Not-only-but-also | "not only fast but also safe" | Keep the claim that matters |
| Rule of three | "fast, reliable, and secure"; three identical-shape bullets | Cut to the one or two that carry load; break symmetry |
| Strawman antithesis | "While other tools struggle, X ..." | Name the comparison or drop it |
| Rhetorical-question transition | "So why does this matter?" | Answer directly; delete the question |
| Meta-narration | "In this guide, we'll explore", "Let's dive in", "Now that we've covered X" | Delete; navigation is the TOC's job |
| Heading echo | First sentence restates the heading | Start with the first new fact |
| Summary closer | "In conclusion", "To wrap up", re-listing the sections | End on the last fact |
| Ta-da pivot | "But here's the truth", "here's the kicker" | "But" |
| Bold-lead-in bullet symmetry | `**Speed:** one sentence` × 6, identical shape, near-zero content | Merge into prose or keep only bullets with distinct substance |
| Sycophantic opener / cheery closer | "Great question!", "I hope this helps", "Happy coding!" | Delete — chat-session leakage |
| Hedge stacking | "can help to potentially reduce" | One verb; commit or cut the claim |
| False range | "from beef to chicken", "from startups to enterprises" when no scale exists | List the actual items or name the real dimension |
| Vague attribution | "experts agree", "industry reports", "observers note" | Name the source or own the claim |
| Audience straddle | "whether you're a beginner or a seasoned pro" | Write for the one audience the doc has |
| Outline conclusion | "Challenges and Future Outlook", "Despite these challenges ... remains" | Cut speculation; end sections when the facts end |

Sources: Wikipedia's negative-parallelism and rule-of-three sections (above),
practitioner catalogs
(<https://copyadscontent.com/signs-of-ai-writing/>,
<https://library.etbi.ie/sources2/aisigns>,
<https://huntingthemuse.net/library/how-to-tell-if-writing-is-ai>).

## Vocabulary tells

Corpus studies isolated the words below by measuring frequency jumps after
ChatGPT's release. Kobak et al., 15M PubMed abstracts, found 379 style words
with elevated 2024 frequency — the excess is verbs and adjectives, not
content nouns (<https://arxiv.org/abs/2406.07016>, Science Advances 2025).
Liang et al. did the same for AI-conference peer reviews and put the
LLM-modified fraction at 6.5–16.9% (<https://arxiv.org/abs/2403.07183>,
ICML 2024).

Highest-signal markers (fold-increase or excess frequency from those papers):

```text
delves        28.0x   (Kobak)     meticulous    34.7x   (Liang)
underscores   13.8x   (Kobak)     intricate     11.2x   (Liang)
showcasing    10.7x   (Kobak)     commendable    9.8x   (Liang)
potential  crucial  findings  comprehensive  insights  notably
enhancing  exhibited  particularly  additionally  across  within
```

Wikipedia's era-tracked vocabulary (rotates by model generation; see
"Durable vs era-bound"):

```text
2023–mid-2024: delve, tapestry, testament, landscape, interplay, boasts,
               garner, intricate, pivotal, vibrant, meticulous, underscore
mid-2024–2025: fostering, showcasing, highlighting, align with, enduring,
               bolstered, emphasizing, enhance, crucial, pivotal, vibrant
mid-2025+:     emphasizing, enhance, highlighting, showcasing
```

Adjacent patterns, same fix — replace with the concrete verb or noun:

- Copula avoidance: `serves as`, `stands as`, `functions as`, `represents`
  for "is"; `boasts`, `features`, `offers`, `maintains` for "has". LLM text
  measurably suppresses plain "is/are" (Wikipedia catalog, above).
- Ability framing: `allows you to`, `enables`, `is designed to`, `aims to` —
  write what it does: moves, records, refuses.
- Significance inflation: `plays a vital role`, `testament to`, `underscores
  the importance of`, `reflects broader trends` — state the fact; let the
  reader weigh it.
- Textbook connectors: `moreover`, `furthermore`, `additionally` opening
  consecutive sentences — reorder so the logic carries itself.

The `slop-lint.py` E2 lexicon owns the mechanical ban list; this section is
for review judgment on words the lint cannot ban (most are legitimate in
isolation — "potential" and "findings" are ordinary English; density is the
signal).

## Formatting and punctuation tells

| Tell | Fix |
|---|---|
| Em-dash density: several dramatic pivots per page | Keep em dashes that mark real asides; most become commas, colons, or two sentences |
| Curly quotes/apostrophes in a repo that types straight ones | Normalize; they betray pasted chatbot output |
| Emoji as list markers or in headings | Delete (slop-lint W2) |
| Title Case In Every Heading | Sentence case unless house style says otherwise |
| Bold spray: every occurrence of chosen terms bolded, "key takeaway" styling | Bold at most first definitional use |
| Inline-header list: bullet + bold term + colon + sentence, repeated | Prose, or a table when there are real columns |
| Skipped heading levels (H2 → H4); horizontal rules before headings | Fix the hierarchy; delete the rules |
| Hyphens where ranges need en dashes, alongside heavy em-dash use | Typographic inconsistency reads generated |
| Tables wrapping what is actually one sentence of prose | Unwrap |

Source: Wikipedia catalog style/markup sections;
em-dash discourse in
<https://www.washingtonpost.com/technology/2025/04/09/ai-em-dash-writing-punctuation-chatgpt/>.

## Content-shape tells

- Fabricated or damaged citations: DOIs that resolve to unrelated papers,
  invented ISBNs, dead URLs, book cites with no page numbers, `utm_source=`
  tracking junk, and raw assistant artifacts (`oaicite`, `contentReference`,
  `[cite: 1]`, `grok_card`). Verify every reference you did not fetch
  yourself (Wikipedia citation section, above).
- Chat-session leakage: knowledge-cutoff disclaimers ("As of my last
  update"), refusal fragments, "As an AI", placeholder text ("This section
  would ..."). Delete on sight; then audit the surrounding prose, which was
  pasted from the same session.
- Fake specificity: "over 100+", "countless", "numerous", "a wide range of".
  Give the number or drop the quantifier.
- Adjective-per-noun spray: every noun wears a modifier. Keep adjectives
  that carry load ("destructive", "reversible"); cut decoration.
- Anthropomorphism: "the app understands your workflow". The app detects,
  matches, records, refuses.
- Elegant variation: synonym cycling to avoid repeating a name (repetition <!-- write-docs:allow E2 -->
  penalty artifact). Repeat the noun; precision beats variety.
- Padded symmetry: sections stretched to match sibling length; invented
  FAQ/Tips/Troubleshooting for problems that do not exist. Two sentences is
  a fine section.
- Both-sides filler: "however, it's worth noting that ..." balancing a claim
  nobody contested. Take the position the evidence supports.
- Superficial -ing analysis: trailing clauses that fake insight —
  "..., highlighting the importance of X", "..., ensuring reliability".
  Either the analysis is a fact (state it as one) or it is air.

## Stylometric properties

What detectors measure (GPTZero-class:
<https://gptzero.me/news/how-ai-detectors-work/>,
<https://gptzero.me/news/perplexity-and-burstiness-what-is-it/>):

- Low perplexity — each next word is the one a language model would predict.
- Low burstiness — uniform sentence length and structure; GPTZero computes
  it as the standard deviation of per-sentence perplexity.
- Low lexical diversity and a preference for common syntactic frames;
  predictable function-word sequences.

You cannot edit "perplexity" directly, but its causes are the tells above:
stock transitions, symmetric structure, hedged medium-strength claims.
Direct rewrite moves:

- Vary rhythm deliberately: follow a long sentence with a short one that
  carries the load-bearing fact. Metronomic paragraphs read generated even
  when every sentence is fine.
- Break structural symmetry: unequal bullet lengths, a section that is one
  line, an aside where it belongs rather than where the template wants it.
- Replace the predictable word when a more exact one exists — exactness,
  not thesaurus variety, is what raises information density.
- Caveat: formal and non-native human prose also scores low on these
  metrics. Treat detector output as a pointer to passages needing a
  specificity pass, never as proof of authorship.

## Durable vs era-bound tells

Era-bound — decay as vendors patch and vocabularies rotate:

- Marker-word lists. "delve" peaked 2023–24 and fell once mocked; <!-- write-docs:allow E2 -->
  Wikipedia now tracks vocabulary in dated bands (see above).
- Em-dash overuse: OpenAI shipped instruction-following suppression in
  November 2025; the public panic made humans self-censor the character too
  (Washington Post, above).
- Politeness boilerplate: "Certainly!", "I hope this helps", "As an AI
  language model" — chat-interface era; API- and agent-generated text
  rarely contains them.
- Vendor-specific citation artifacts (`oaicite` et al.) change with every
  product release.

Durable — produced by helpfulness training itself, stable across
generations:

- Structural symmetry and the rule of three.
- Hedge stacking and both-sides filler.
- Vague attribution and significance inflation.
- Uniform sentence rhythm.
- Padding to expected shape instead of stopping when facts run out.

Weight durable tells in review; treat any memorized word list as
perishable and re-derive it from current sources when it matters.

## Human counter-signals and the register test

Expert prose under-produced by models — presence of these is evidence of a
human author, and injecting them is the strongest de-slopping move
(<https://gptzero.me/news/how-to-write-like-a-human/>,
<https://matthewvollmer.substack.com/p/i-asked-the-machine-to-tell-on-itself>):

- Non-round numbers from real measurement: "open rate fell from 31% to 22%
  in three weeks", not "results varied".
- Named specifics: the actual client, tool version, file path, failure.
- A stance without hedges: "Subject lines over eight words tank open rates.
  Keep them short."
- An opinionated cut: "We don't support X. Use Y." — models pad; experts
  refuse.
- Domain shorthand used without explanation, calibrated to the stated
  audience.
- Asymmetric structure: the important point gets three paragraphs, the
  minor one gets a clause.
- A concrete anecdote or a mistake admitted with its cost.

Register test, applied last: would a named expert ship this text to peers
under their own byline? If any sentence survives only because it sounds
finished, it fails.
