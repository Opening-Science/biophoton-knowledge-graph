# Biophoton Field Map — Milestone 2 Checkpoint

_OpenAlex snapshot: harvested 2026-07-19/20. Universe = 14807 works in the coupling graph._

## 1. The field-boundary question (the analytical ask)

Sonoluminescence / acoustic-cavitation seed works land in bibliographic-coupling community **4**, while the UPE core (Cifra / Popp / Van Wijk / Kobayashi) lands in community **0** — **distinct communities**.

- Sonoluminescence seed works (52): community distribution {'4': 34, '1': 10, '2': 1, '6': 2}
- UPE-core seed works: distribution {'0': 36}

This empirically confirms the physics (single-bubble sonoluminescence, cavitation) is an **adjacency**, not part of the biophoton/UPE core — answering the scope question from the map itself rather than by pre-filtering.

## 2. Sub-field communities (bibliographic coupling)

11 communities over 14807 works (2,392,824 coupling edges). Largest communities:

### Community 0 — 5193 works, 125 seeds, median year 2012  ← **UPE / biophoton core**
- **Topics:** Biofield Effects and Biophysics, bioluminescence and chemiluminescence research, Photoreceptor and optogenetics research, Electromagnetic Fields and Biological Effects, Neural dynamics and brain function
- **Top authors:** Michael A. Persinger, Jack A. Tuszyński, Michal Cifra, Ignat Ignatov, Agata Scordino, Francesco Musumeci
- **Most-cited work:** Hallmarks of Cancer: The Next Generation (2011.0, 66806 cites)

### Community 1 — 3016 works, 13 seeds, median year 2014
- **Topics:** Ultrasound and Cavitation Phenomena, Advanced oxidation water treatment, Ultrasound and Hyperthermia Applications, Nanoplatforms for cancer theranostics, Innovative Microfluidic and Catalytic Techniques Innovation
- **Top authors:** Muthupandian Ashokkumar, Oualid Hamdaoui, Slimane Merouani, Kyuichi Yasui, Kenneth S. Suslick, Franz Grieser
- **Most-cited work:** Biodiesel from microalgae (2007.0, 9282 cites)

### Community 2 — 2869 works, 1 seeds, median year 2015
- **Topics:** Ultrasound and Cavitation Phenomena, Ultrasound and Hyperthermia Applications, Cavitation Phenomena in Pumps, Minerals Flotation and Separation Techniques, Fluid Dynamics and Mixing
- **Top authors:** Michel Versluis, Claus‐Dieter Ohl, Detlef Lohse, Werner Lauterborn, Nico de Jong, Yuning Zhang
- **Most-cited work:** <i>Hydrodynamic and Hydromagnetic Stability</i> (1962.0, 10446 cites)

### Community 3 — 1974 works, 9 seeds, median year 2011
- **Topics:** Mitochondrial Function and Pathology, Skin Protection and Aging, Redox biology and oxidative stress, Nitric Oxide and Endothelin Effects, Plant Stress Responses and Tolerance
- **Top authors:** Rafael Radí, Helmut Sies, Barry Halliwell, Ohára Augusto, Pavel Pospı́šil, Jens J. Thiele
- **Most-cited work:** The Hallmarks of Aging (2013.0, 15043 cites)

### Community 4 — 1154 works, 34 seeds, median year 2007  ← **sonoluminescence / cavitation (adjacency)**
- **Topics:** Ultrasound and Cavitation Phenomena, Quantum Electrodynamics and Casimir Effect, Nuclear Physics and Applications, Ultrasound and Hyperthermia Applications, Electrohydrodynamics and Fluid Dynamics
- **Top authors:** Seth Putterman, Ho‐Young Kwak, Kyuichi Yasui, Detlef Lohse, Weizhong Chen, Г. Л. Шарипов
- **Most-cited work:** Electrogenerated Chemiluminescence and Its Biorelated Applications (2008.0, 2113 cites)

### Community 5 — 452 works, 0 seeds, median year 2011
- **Topics:** Planarian Biology and Electrostimulation, Ion channel regulation and function, Developmental Biology and Gene Regulation, Plant and Biological Electrophysiology Studies, Cancer Cells and Metastasis
- **Top authors:** Michael Levin, Min Zhao, Dany Spencer Adams, Richard B. Borgens, Colin McCaig, Brian Reid
- **Most-cited work:** Putting tumours in context (2001.0, 2171 cites)

### Community 6 — 141 works, 2 seeds, median year 2021
- **Topics:** Minerals Flotation and Separation Techniques, Ultrasound and Cavitation Phenomena, nanoparticles nucleation surface interactions, Industrial Gas Emission Control, Nonlocal and gradient elasticity in micro/nano structures
- **Top authors:** Kyuichi Yasui, Toru Tuziuti, Wataru Kanematsu, Jun Hu, Muidh Alheshibri, Lijuan Zhang
- **Most-cited work:** Principle and applications of microbubble and nanobubble technology for water treatment (2011.0, 1041 cites)

### Community 7 — 2 works, 0 seeds, median year 1997
- **Topics:** Spectroscopy and Chemometric Analyses, Water Quality Monitoring and Analysis
- **Top authors:** James M. Gallas, M. Eisner, Xianglei Cheng, Lixia Zhao, Xu Wang, Jin‐Ming Lin
- **Most-cited work:** FLUORESCENCE OF MELANIN‐DEPENDENCE UPON EXCITATION WAVELENGTH AND CONCENTRATION (1987.0, 105 cites)

### Community 8 — 2 works, 0 seeds, median year 1998
- **Topics:** Photosynthetic Processes and Mechanisms, Photoreceptor and optogenetics research
- **Top authors:** Guenter Albrecht‐Buehler
- **Most-cited work:** Autofluorescence of Live Purple Bacteria in the Near Infrared (1997.0, 34 cites)

### Community 9 — 2 works, 0 seeds, median year 2001
- **Topics:** Microtubule and mitosis dynamics, Electron Spin Resonance Studies
- **Top authors:** Shyam Sundar Maity, Lalita Das, Sanjib Ghosh, Suranjana Guha, Satinder S. Rawat, Amitabha Chattopadhyay
- **Most-cited work:** Tubulin Conformation and Dynamics:  A Red Edge Excitation Shift Study (1996.0, 60 cites)

## 3. Co-authorship structure

- 39,312 authors, 154,448 co-authorship edges, 5,918 research-group communities (labs/collaborations).

## 4. §10 verification

- **Seed coverage:** 245/263 seeds resolved (target ≥240 — PASS).
- **Boundary sanity:** sonoluminescence separates from UPE core — PASS.
- **Known-author spot checks** (must appear with sane institution + high seed-connectedness):

| Author | Seed works | Institution | Country | ORCID | Total works | Cited by |
|---|---|---|---|---|---|---|
| Michal Cifra | 15 | Czech Academy of Sciences, Insti | CZ | 0000-0002-8853-9523 | 163 | 2,571 |
| Masaki Kobayashi | 10 | NTT Basic Research Laboratories | JP | 0000-0002-9968-1410 | 252 | 4,226 |
| Roeland Van Wijk | 9 |  |  |  | 1 | 31 |
| Eduard van Wijk | 7 | Laguna Research | US | 0000-0002-4432-3042 | 53 | 676 |
| Felix Scholkmann | 6 | University of Bern | CH | 0000-0002-1748-4852 | 253 | 10,695 |
| Eduard P.A. Van Wijk | 5 |  |  |  | 40 | 1,150 |
| Vahid Salari | 5 | University of Calgary | CA | 0000-0001-7908-0696 | 116 | 1,291 |
| Francesco Musumeci | 5 | Politecnico di Milano | IT | 0000-0002-5554-3366 | 165 | 1,815 |
| F. A. Popp | 4 |  |  |  | 105 | 2,053 |
| Fritz-Albert Popp | 2 |  |  |  | 38 | 1,033 |
| Eduard P A Van Wijk | 1 |  |  |  | 1 | 10 |
| M. Kobayashi | 1 | Tohoku University | JP | 0009-0008-3148-143X | 54 | 514 |

## 5. Deliverables so far

- `data/db/fieldmap.sqlite` — queryable DB (works, authors, institutions, work_authors, topics, citation/coauthor edges).
- `data/exports/*.parquet|csv` — all tables.
- `data/exports/*.graphml` — coauthorship, coupling, cocitation, topic graphs (open in Gephi).
- `data/exports/work_communities.csv` — per-work sub-field community assignment.
- `run_log.md` — every prune/cap count.
