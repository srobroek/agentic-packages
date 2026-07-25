# BIOME -- the demo, orchestrated

**What it is:** a single self-contained `biome.html` (zero deps, opens offline in
any browser) containing a living, evolving digital ecosystem -- particle-life
creatures with mutating genomes that genuinely evolve and speciate in real time,
a generative WebAudio soundscape that reflects the ecosystem's health, and an
interactive layer to seed and perturb the world and watch emergence happen.

**Why "an AI built this?!":** the complexity is emergent, not scripted -- real
evolution (populations rise and crash, species appear and go extinct) unfolding
live, in one shareable file.

**How it was built -- via our own orchestrator (bead-as-brief v2):**
Isolated playground `/tmp/demo-magnum` (own git + beads, prefix `demo-magnum`).
Epic `demo-magnum-0c6`. Five nodes:

- N1 `life-engine.js` -- artificial-life + genome + evolution core (high tier)
- N2 `renderer.js` -- bioluminescent canvas renderer (parallel)
- N3 `audio.js` -- generative WebAudio soundscape (parallel)
- N4 `hud.js` -- live stats, species tree, controls (parallel)
- N5 `biome.html` -- integrate all four into one file (blocked on N1--N4)

Four `builder` domain-specialists spawned in parallel, each activated by only
`CLAIM <bead-id>`, reading its BRIEF from the bead, honoring a shared
`window.BIOME.*` integration contract. Then N5 integrates. Then it gets doubled.

## Run log

(iteration observations appended as the run proceeds)
