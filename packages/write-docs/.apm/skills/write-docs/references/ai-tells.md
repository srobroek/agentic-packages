# AI Tells

Last researched: 2026-07.

Markers that flag prose as machine-generated, with the rewrite move for each.
No single tell proves anything -- humans wrote the training data -- but tells
cluster; three or more in one passage is a rewrite signal
(<https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing>).
Rewrite the fact densely; delete only when the sentence carries no fact.

## Why structure outranks vocabulary

Vendors patch lexical tells. "Delve" peaked in 2023-24, fell once mocked, and <!-- write-docs:allow E2 -->
dropped off sharply in 2025 (Wikipedia catalog, above); OpenAI shipped
instruction-following em-dash suppression in late-2025 frontier models
(<https://techcrunch.com/2025/11/14/openai-says-its-fixed-chatgpts-em-dash-problem/>);
a Washington Post analysis of 328,744 ChatGPT messages found the cliché
palette rotates each generation
(<https://decrypt.co/348923/5-biggest-tells-something-written-ai>). Any
memorized word list is perishable (see the appendix).

Structural and register tells endure because preference training produces
them: raters reward length, markdown, bulleted symmetry, and confident
even-handedness, so every generation reconverges on the same shapes even as
the vocabulary changes (RLHF Book ch. 18, <https://rlhfbook.com/c/18-style>).
When LinkedIn announced demotion of "contrastive construction" slop in 2026,
the named pattern was structural, not lexical
(<https://www.theregister.com/ai-and-ml/2026/07/09/ai-slop-writing-has-taken-over-the-internet-particularly-linkedin-and-x/5269525>).
Weight everything in the next two sections above any word list.

## Rhetorical-structure tells

| Tell | Looks like | Fix |
|---|---|---|
| Contrastive inversion | "It's not X, it's Y", "This isn't just X -- it's Y", "It's less about X and more about Y" | State what the thing is; cut the strawman. The single most-cited current tell (<https://gc.ai/blog/ai-writing-pattern-to-know-contrastive-negation>) |
| Staccato negative parallel | "No X. No Y. Just Z."; "Not a bug. Not a feature. A design flaw." | One plain sentence naming Z |
| Not-only-but-also | "not only fast but also safe" | Keep the claim that matters |
| Rule of three / tricolon abuse | "fast, reliable, and secure"; three identical-shape bullets; back-to-back tricolons | Cut to the one or two that carry load; break symmetry |
| One-sentence emphasis paragraph | A lone fragment paragraph for drama. "Openly. In a book." | Rejoin the sentence; let the fact carry the weight |
| False-suspense transition | "Here's the thing", "Here's the kicker", "Here's what most people miss" | Delete the drumroll; state the point |
| Fragment-question pivot | "The result? Devastating." | One declarative sentence |
| Strawman antithesis | "While other tools struggle, X ..." | Name the comparison or drop it |
| Rhetorical-question transition | "So why does this matter?" | Answer directly; delete the question |
| Meta-narration | "In this guide, we'll explore", "Let's unpack this", "Let's dive in" | Delete; navigation is the TOC's job |
| Heading echo | First sentence restates the heading | Start with the first new fact |
| Summary closer | "In conclusion", "To wrap up", re-listing the sections | End on the last fact |
| Listicle in a trench coat | "The first wall is... The second wall is..." -- a numbered list wearing prose | Either a real list or real prose with connective logic |
| Anaphora abuse | "They assume that... They assume that... They assume that..." | Say it once; merge the objects |
| Analogy-stack authority | "Apple didn't build Uber. Facebook didn't build Spotify." | One apt comparison, or none |
| Invented concept label | "the supervision paradox", "workload creep" coined mid-doc and never defined | Use the plain description; coin nothing |
| Cataphoric numbered lead-in | Announcing a count before enumerating: "Three pillars support this", "falls into three categories" | Let the list carry its own length; cut the forecast |
| Hollow acknowledgment | Naming a problem then declining to solve it: "names the risk without addressing it", "all diagnosis, no treatment" | Solve it, or cut the paragraph that raises it |
| Absolute assertion | "the only way to", "the single most important", "make no mistake" | State the claim with its actual scope. The mirror of hedge stacking -- over-commitment reads as generated too |
| Think-of-it-as reflex | "Think of it like a highway system for data" | Explain the actual mechanism once; cut the teacher voice |
| Bold-lead-in bullet symmetry | `**Speed:** one sentence` × 6, identical shape, near-zero content | Merge into prose or keep only bullets with distinct substance |
| Hedge stacking | "can help to potentially reduce" | One verb; commit or cut the claim |
| False range | "from beef to chicken", "from startups to enterprises" when no scale exists | List the actual items or name the real dimension |
| Vague attribution | "experts agree", "industry reports", "observers note" | Name the source or own the claim |
| Audience straddle | "whether you're a beginner or a seasoned pro" | Write for the one audience the doc has |
| Outline conclusion | "Challenges and Future Outlook", "Despite these challenges ... remains" | Cut speculation; end sections when the facts end |

Sources: Wikipedia catalog (above); the community trope directory
<https://tropes.fyi/> (contrastive patterns, false suspense, fragment
cadence); practitioner catalogs
(<https://www.oliviacal.com/post/ai-writing-tells>,
<https://medium.com/@tdoherty_96508/a-field-guide-to-terrible-ai-writing-6a83ddb6a141>).

## Register tells (current generation, 2025-26)

The chat-assistant register that survived lexical patching. Each entry is a
voice, not a word -- synonym-swapping does not remove it.

- Faux-candor pivot: "Here's the thing:", "honestly?", "let's be real",
  performative vulnerability that reads polished and risk-free
  (tropes.fyi "False Vulnerability"). Fix: cut the intimacy performance;
  candor is the unhedged claim itself.
- Punchy-fragment cadence: TED-talk rhythm -- short dramatic fragments,
  slow build to a Big Insight, repetition for effect. Fix: rejoin fragments;
  one long sentence and one short one beat six fragments.
- Intensifier tics: "genuinely", "actually", "quietly excellent", "deeply",
  "fundamentally", "remarkably" -- unearned emotion announced instead of
  earned (tropes.fyi "magic adverbs";
  <https://github.com/conorbronsdon/avoid-ai-writing>). Fix: drop the
  intensifier, add the specific claim that would justify it.
- Corporate-analytic filler: "at its core", "it's worth noting",
  "importantly", "nuanced", "granular", "lean into" -- analysis-flavored
  packaging around no analysis. Fix: delete the wrapper; keep the noun.
- Over-formatting reflex: headers, tables, and bold-colon bullets where two
  sentences of prose would do -- a direct reward-model artifact (RLHF Book
  ch. 18; per-model formatting fingerprints in
  <https://arxiv.org/abs/2502.12150>). Fix: format only when the data has
  columns or the items are parallel and independent.
- Uniform paragraph mass: every paragraph three sentences of 15-20 words,
  metronomic transitions, no tangents. Fix: vary length deliberately; let
  one point take three paragraphs and the next one clause.
- Hedged symmetry: every claim balanced by its counter-claim nobody made;
  comprehensive even-handedness where a human picks a side. Fix: take the <!-- write-docs:allow E2 -->
  position the evidence supports; cut the ballast.
- Sycophantic meta-residue: "Great question!", "You're absolutely right",
  qualifier-then-immediate-reassurance stacks -- chat-approval training
  leaking into shipped prose. Fix: delete; then audit the surrounding text,
  which came from the same session.
- Figurative-verb verdict: judgement delivered as metaphor rather than claim --
  "the point lands", "the argument holds", "stays quiet about", "punches above
  its weight", "the abstraction earns its keep". The construction carries the
  verdict so no evidence has to. Fix: state the judgement literally, with the
  observation that supports it. Distinctly 2026 register -- it survived the
  lexical patching that killed the 2023-24 adjective bands.
- Urgency inflation: "cannot be overstated", "more important than ever", "at an
  inflection point", "in an increasingly complex world" -- stakes asserted to
  substitute for consequence. Fix: name what breaks if the reader ignores it,
  or drop the framing.
- Organic-consequence framing: "falls out naturally", "emerges organically",
  "a natural consequence of" -- presenting a designed decision as something that
  happened by itself, which erases the agent who chose it. Fix: say the choice
  was made, and why.
- Anthropomorphised justification: "earns its keep", "pulls its weight",
  "load-bearing", "deserves a closer look", "settles the debate" -- a component
  granted intent so its value needs no argument. Fix: state the measured
  property. (Broader than the anthropomorphism entry under content-shape tells,
  which covers subjects *acting*; this covers subjects *deserving*.)

Model fingerprints inside this register drift fast: as of 2026 Wikipedia
tracks Grok-specific overuse ("empirical", "correlate") and notes hedged
qualifier-reassurance stacking as characteristic of Claude
(<https://matthewvollmer.substack.com/p/i-asked-the-machine-to-tell-on-itself>).
Treat per-model attributions as snapshots, not durable rules.

## Formatting and punctuation tells

| Tell | Fix |
|---|---|
| Em-dash density: several dramatic pivots per page | Keep em dashes that mark real asides; most become commas, colons, or two sentences. Suppressible since late 2025, so absence proves nothing; density still signals |
| Hyphen-swap: hyphens doing em-dash work at em-dash density | Same fix -- a find-and-replace on a tell is still the tell |
| Curly quotes/apostrophes in a repo that types straight ones | Normalize; they betray pasted chatbot output |
| Emoji as list markers or in headings | Delete (WriteDocs.EmojiHeading) |
| Title Case In Every Heading | Sentence case unless house style says otherwise |
| Bold spray: every occurrence of chosen terms bolded, "key takeaway" styling | Bold at most first definitional use |
| Inline-header list: bullet + bold term + colon + sentence, repeated | Prose, or a table when there are real columns |
| Skipped heading levels (H2 → H4); horizontal rules before headings | Fix the hierarchy; delete the rules |
| Hyphens where ranges need en dashes, alongside heavy em-dash use | Typographic inconsistency reads generated |
| Tables wrapping what is actually one sentence of prose | Unwrap |
| Italicised copula for manufactured profundity: `*is*`, `*not*`, `*the*` emphasised mid-sentence | Delete the emphasis; if the contrast is real, rewrite so word order carries it |
| Cross-reference signposting: "as mentioned above", "as we'll see", "recall that" | Delete. It assumes linear reading and is usually false in a doc with a TOC |

Source: Wikipedia catalog style/markup sections; em-dash suppression in
<https://techcrunch.com/2025/11/14/openai-says-its-fixed-chatgpts-em-dash-problem/>.

## Content-shape tells

- Fabricated or damaged citations: DOIs that resolve to unrelated papers,
  invented ISBNs, dead URLs, book cites with no page numbers, `utm_source=`
  tracking junk, and raw assistant artifacts (`oaicite`, `contentReference`,
  `[cite: 1]`, `grok_card`). Verify every reference you did not fetch
  yourself (Wikipedia citation section, above).
- Chat-session leakage: knowledge-cutoff disclaimers ("As of my last
  update"), refusal fragments, "As an AI", placeholder text ("This section <!-- write-docs:allow E5 -->
  would ..."). Delete on sight; then audit the surrounding prose, which was
  pasted from the same session. Mechanised as slop-lint E5 -- the one tell here
  that is never a style judgement, so it errors in every genre.
- Fake specificity: "over 100+", "countless", "numerous", "a wide range of".
  Give the number or drop the quantifier.
- Adjective-per-noun spray: every noun wears a modifier. Keep adjectives
  that carry load ("destructive", "reversible"); cut decoration.
- Anthropomorphism: "the app understands your workflow". The app detects,
  matches, records, refuses.
- Elegant variation: synonym cycling to avoid repeating a name (repetition <!-- write-docs:allow E2 -->
  penalty artifact). Repeat the noun; precision beats variety.
- One-point dilution: the same argument restated eight ways across a long
  doc, each restatement in a fresh metaphor. Say it once; stop.
- Padded symmetry: sections stretched to match sibling length; invented
  FAQ/Tips/Troubleshooting for problems that do not exist. Two sentences is
  a fine section.
- Superficial -ing analysis: trailing clauses that fake insight --
  "..., highlighting the importance of X", "..., ensuring reliability".
  Either the analysis is a fact (state it as one) or it is air.
- Durable vocabulary habits (shapes, not marker words): copula avoidance
  ("serves as", "stands as", "represents" for "is"; "boasts", "offers" for
  "has"); ability framing ("allows you to", "is designed to" -- write what
  it does); significance inflation ("plays a vital role", "testament to");
  textbook connectors ("moreover", "furthermore" opening consecutive
  sentences). Replace with the concrete verb or noun.

## Stylometric properties

What detectors measure (GPTZero-class:
<https://gptzero.me/news/how-ai-detectors-work/>,
<https://gptzero.me/news/perplexity-and-burstiness-what-is-it/>):

- Low perplexity -- each next word is the one a language model would predict.
- Low burstiness -- uniform sentence length and structure; GPTZero computes
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
- Replace the predictable word when a more exact one exists -- exactness,
  not thesaurus variety, is what raises information density.
- Caveat: formal and non-native human prose also scores low on these
  metrics, and 2025 research puts unaided human detection at chance. Treat
  detector output as a pointer to passages needing a specificity pass,
  never as proof of authorship.

## Human counter-signals and the register test

Expert prose under-produced by models -- presence of these is evidence of a
human author, and injecting them is the strongest de-slopping move
(<https://gptzero.me/news/how-to-write-like-a-human/>,
<https://matthewvollmer.substack.com/p/i-asked-the-machine-to-tell-on-itself>):

- Non-round numbers from real measurement: "open rate fell from 31% to 22%
  in three weeks", not "results varied".
- Named specifics: the actual client, tool version, file path, failure.
- A stance without hedges: "Subject lines over eight words tank open rates.
  Keep them short."
- An opinionated cut: "We don't support X. Use Y." -- models pad; experts
  refuse.
- Domain shorthand used without explanation, calibrated to the stated
  audience.
- Asymmetric structure: the important point gets three paragraphs, the
  minor one gets a clause.
- A concrete anecdote or a mistake admitted with its cost.

Register test, applied last: would a named expert ship this text to peers
under their own byline? If any sentence survives only because it sounds
finished, it fails.

## Appendix: historical lexical era-bands (unreliable for current models)

Marker-word lists date fast: each band below was patched or mocked out of
the next model generation, so absence proves nothing and presence mainly
indicates unedited output from that band's era. Do not weight these against
2025+ text.

```text
2023-mid-2024: delve, tapestry, testament, landscape, interplay, boasts,
               garner, intricate, pivotal, vibrant, meticulous, underscore
mid-2024-2025: fostering, showcasing, highlighting, align with, enduring,
               bolstered, emphasizing, enhance, crucial, pivotal, vibrant
mid-2025+:     emphasizing, enhance, highlighting, showcasing
```

Provenance: Wikipedia's era-tracked bands (above); corpus studies that
measured post-ChatGPT frequency jumps -- Kobak et al., 15M PubMed abstracts,
379 style words with elevated 2024 frequency, the excess in verbs and
adjectives ("delves" 28.0x, "underscores" 13.8x; <!-- write-docs:allow E2 -->
<https://arxiv.org/abs/2406.07016>) and Liang et al. on AI-conference peer
reviews ("meticulous" 34.7x, "intricate" 11.2x;
<https://arxiv.org/abs/2403.07183>).

The `WriteDocs.SlopLexicon` Vale rule owns the mechanical ban list. Words in
these bands are still worth cutting when they displace a more exact word -- but
as style debt, not as authorship evidence. The upstream
`ai-tells.OverusedVocabulary` rule is disabled precisely because it is this
appendix's dead band shipped as an error.

## Refreshing this document

Lexical sections decay per model generation; structural and register
sections endure. When the Last-researched date is more than one model
generation (~12 months) old:

- Re-pull the current revision of Wikipedia's "Signs of AI writing" -- its
  era bands and model-specific notes are actively maintained.
- Sample recent practitioner catalogs (tropes.fyi or successors, editor and
  writing-community threads) for the newest generation's register.
- Check for new lexical-frequency corpus studies (Kobak/Liang-style) and
  for vendor steerability changes that retire a formatting tell.
- Rotate the era-band appendix; leave the structural, register, stylometric,
  and counter-signal sections unless a source shows a generation broke them.
