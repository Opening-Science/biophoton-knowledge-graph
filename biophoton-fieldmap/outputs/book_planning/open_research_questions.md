# Major open research questions in the biophoton / UPE field

**Derivation.** Mined from the full-text corpus (4,348 extracted works
covering 63.5% of the field's open-access output, plus curated closed-access
key papers): 4,916 sentences flagging open problems, controversies,
measurement gaps and future-work directions, filtered to the UPE core and
ROS wing and hand-synthesised into seven questions. Every claim below is
anchored to verbatim quotes with work id, page and DOI in
`open_question_statements.md`; quotes here are abridged with `[...]`.
This document states what the *field itself* says it does not know.

---

## Q1. What actually generates the photons — and why is the UV part still unexplained?

The consensus mechanism (ROS-driven lipid peroxidation → triplet carbonyls
and singlet oxygen → visible/near-IR emission) accounts for the bulk
spectrum, but its edges are open:

- "the origin of UPE in the UV region (especially < 350 nm) is not
  completely understood yet" — Madl 2017, p.3, `W2752165143`
- "Although the exact mechanism of biophoton production is still
  unclear [...] there is increasing evidence that cells emit these photons"
  — Pietruszka 2024, `W4404582469`
- "Although mechanisms of cellular UPE generation remain unclear [9], it is
  now established that all living cells emit minuscule numbers of photons"
  — Babcock 2024, p.1, `W4404871602`
- Even inside chemiluminescence chemistry, the decisive elementary steps
  are unassigned: "the explicit nature of this transformation
  (isomerization or dissociation) remains unclear" — Fedorova 2006,
  `W2953285197`

**Why it matters for the book:** UV UPE is the historical root (Gurwitsch's
mitogenetic radiation) *and* the least-instrumented band — UV photon rates
are lowest and detectors weakest there. Mechanism and metrology are the
same problem seen from two sides.

**What would settle it:** spectrally resolved emission with calibrated,
per-band absolute photon fluxes across biological models, tied to targeted
chemical perturbation of candidate ROS pathways (the Pospíšil–Prasad
program, extended below 350 nm).

## Q2. Is UPE coherent — and can photocount statistics ever decide?

The Popp-school claim that biological emission is a coherent field remains
the field's oldest unresolved theoretical dispute:

- "While there is some consensus about intensity and spectrum of UPE,
  claims about statistical properties of UPE are very controversial" —
  Cifra 2015, p.1, `W2141663490`
- "his interpretations [of] experimental results on UPE photocount
  statistics in terms of coherent states are controversial and [...] not
  generally accepted" — Cifra 2015, p.14 (on Popp)
- "biophoton emissions [...] are speculated to be coherent and
  highly-structured [...] this speculation has been subject to much debate
  and remains to be determined" — Hoh Kam 2025, `W4415884611`
- "the idea that UPE is coherent is under debate" — Berke 2023,
  `W4386752905`
- The proposed way out is instrumental: "the development of new types of
  photon detectors [...] closer to that of the ideal detectors may bring at
  least partial answers to the open questions about UPE statistical
  properties" — Cifra 2015, p.24

**Status:** the live theoretical work has moved from the Popp school
(no longer active in the corpus) to quantum-biology-adjacent groups
(Kurian `W2748679677`: "whether coherent energy transfer in tubulin and
microtubules has a biological role remains open"; Celardo, Babcock, Simon).

**What would settle it:** photon-number-resolving detection with
characterised quantum efficiency and dead-time, on standard biological
references, analysed with pre-registered statistical models — a
detector-metrology problem before it is a biology problem.

## Q3. Byproduct or signal? The functional-role question

The single most-repeated open question in the corpus, and explicitly
undecided in the newest literature:

- "Whether UPE is a byproduct of biological metabolism or has some
  informational or functional role [...] remain[s] unclear" — Berke
  2023/2024, `W4386752905`, `W4400260683`
- "The question about a functional role for weak intrinsic UPE has a rather
  long tradition [...] still very speculative and a matter of debate" —
  Zamani 2017, `W2618829643`
- "Although cellular signaling via UPE is well-documented, critics have
  argued that if it exists as a general physiological effect, then it must
  employ mechanisms that are not yet understood to exist in living cells" —
  Babcock 2024, p.10, `W4404871602`
- The century-old anchor dispute is explicitly unreproduced: "there is a
  definitive need to reproduce both positive and negative control
  experiments with modern lab equipment and theory" — Babcock 2024, p.10
  (on Gurwitsch's UV-induced mitosis)
- "The biological significance of such displays are still not understood"
  — Srivastava 2021, `W3161171972`

**What would settle it:** blinded, multi-lab replication of one
best-case cell-to-cell effect (mitogenetic or otherwise) with optical-only
coupling, pre-registered protocols, and — again — absolutely calibrated
photon budgets to show the receiver plausibly gets enough photons.

## Q4. Does the brain's UPE mean anything — and can it even be measured from outside the head?

The youngest strand (median year 2021) carries the sharpest current
controversy:

- "Biophotons have been experimentally shown to be produced in the brain,
  yet their purpose is not understood" — Zarkeshian 2022, `W4310701752`
- "a recent controversial experiment [...] is the relevance of intelligence
  and UPE in the brain" — Esmaeilpour 2020, `W2999575750`
- The 2026 extracranial-detection dispute (curated, closed-access; full
  text in the knowledgebase): reported background exceeding signal "raises
  the question whether the detected signal might be dominated by something
  other than UPE"; skull transmission "close to zero below 580 nm" while
  "the detectors are optimized for wavelengths that cannot realistically
  pass through the scalp and skull"; apparent temporal structure "could be
  due to statistical artifacts [...] modulation of detector noise,
  background light fluctuations, variations in detector efficiency, head
  motion" — Salari 2026, `W7168813583` (pp. 2–5)
- "Future studies should be directed toward addressing specific roles for
  biophotons in the brain" — Tonello 2018, `W2755140939`

**What would settle it:** tissue-optics-informed detection (wavelength
bands that actually transmit), photon-budget modelling before data
collection, and artifact controls of the kind Salari 2026 enumerates.
This is the chapter where the book can show critical rigour *inside* the
field, not against it.

## Q5. The metrology hole: no calibration, no absolute units, no comparability

The corpus's most consequential systemic gap — and the direct evidence base
for the book's measurement thesis:

- "papers on luminescence-based detection methods rarely report on light
  signals in absolute numbers of photons, and never report on detection
  limits (LOD) in units of the density of photon emission rate, thus
  precluding any direct sensitivity comparison" — Khaoua 2021, p.8,
  `W3161989600`
- "UPE is still more of a technical curiosity than a reliable biomarker in
  the absence of standardization" — Amjad 2025, `W4417459026`
- "the absence of standardized protocols for clinical measurement" listed
  among key experimental constraints — Sá 2026, `W7165757820`
- The field's own reference volume on its history: "many authors
  experienced periods of unexplained irreproducibility of their results" —
  Volodyaev et al. 2023 (Springer volume), p.17, `W4389669809`
- Instrument constants are still treated as unknowable: "k is an unknown
  instrumental constant which depends on the absolute quantum efficiency of
  the photomultiplier, the efficiency of the collection optics, etc." —
  Cheson 1976, `W2048659050` — a sentence that could be written unchanged
  in most 2025 papers.

**Why this is tractable now:** the calibration chain the field lacks
already exists in single-photon radiometry — sub-100 fW detector
calibration (Porrovecchio 2016, Metrologia, `curated/`) and free-running
single-photon-detector efficiency metrology (López 2020, EPJ Quantum
Technology, `curated/`) are solved problems in the metrology community,
which the field map shows has **zero bibliographic contact** with the UPE
literature. Bridging that gap is the book's most concrete, most fundable
agenda item: reference materials, shared dark-count/QE reporting standards,
and one inter-laboratory comparison would convert decades of archived
counts-per-second into comparable science.

## Q6. Can UPE become a clinical biomarker?

Persistent promise, consistently gated on Q5:

- Oxidative-stress imaging of skin and disease models works in-lab
  (Tsuchida 2020 `W3035757108`; Poplová 2023 `W4387077320`), and human UPE
  is proposed as a "non-invasive spectroscopic tool for diagnosis" (Zapata
  2021, `W3126963047`), but:
- "Future studies should prioritize rigorous RCT designs, pre-specified
  primary endpoints, adequate sample sizes, standardized [...] protocols,
  and validation of biophotonic measurement techniques as objective
  biomarkers" — Sá 2026, `W7165757820`
- Delayed-luminescence quality control of medicinal plants is emerging as
  the nearest-term application: "the cultivation process of medicinal
  plants remains outside the quality control system" — Cao 2026,
  `W7122655226`; validation "in field or greenhouse production systems
  with larger sample sizes" is the stated next step — Wang 2025,
  `W4416135829`

**What would settle it:** one pre-registered clinical validation study of a
single endpoint (e.g. skin oxidative status) with calibrated instruments —
which again presupposes Q5.

## Q7. Imaging: from counting to pictures

In-vivo imaging is detector-limited, not biology-limited:

- "attempts at in vivo [imaging] have often been hampered by tissue
  scattering or absorption of light, leading to low signal-to-noise
  ratios" — Endo 2020, `W3083575255`
- Identification of the emitting species in planta "will be a major
  challenge in future studies" — Havaux 2022, `W4283824773`
- The instrument frontier (EMCCD → SPAD arrays, photon-number resolution)
  is exactly where quantum-optics instrumentation groups entering the field
  matter most — the neural-UPE strand already shows this influx.

---

## Reading the seven together

Q1–Q4 are the field's *scientific* questions; Q5 is the *infrastructural*
one; Q6–Q7 are *translational*. The corpus shows Q5 is upstream of all of
them: the mechanism dispute (Q1), the coherence dispute (Q2), the
signalling dispute (Q3) and the brain-UPE dispute (Q4) each persist in
significant part because measurements from different laboratories cannot be
compared in absolute terms. That is the book's thesis, now stated by the
field's own literature in its own words — and the two metrology papers in
`literature/curated/` are the imported solution path.

*Sources: `open_question_statements.md` (310 ranked verbatim statements
with provenance); `literature/knowledgebase.sqlite` `statements` table
(4,916 raw). Regenerate with `src/book_planning.py`.*
