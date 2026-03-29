# papyri-linkedin

Prototype workspace for ancient-text named entity extraction and relationship mapping.

## Getting started

1. Clone this repository and `cd papyri-linkedin`
2. Install dependencies: `uv sync`
3. Download the corpus: `uv run python local_loader.py --setup`
   (~2 GB sparse checkout from [papyri/idp.data](https://github.com/papyri/idp.data))
4. Open the notebook: `uv run jupyter notebook corpus_overview.ipynb`

Step 3 downloads ~2 GB and may take several minutes depending on connection speed. The notebook itself runs in 5-8 minutes on the full corpus.

## Technical primer

This project is designed around a lightweight research workflow for papyrological and epigraphic data:

- Papyri.info for document-level metadata and text acquisition
- Trismegistos for identifiers, prosopography, and cross-project linking
- spaCy for baseline named entity recognition and rule-based post-processing
- transformers for higher-accuracy NER or classification when a fine-tuned model is available
- networkx for building graphs that connect documents, people, places, and references

## What success looks like

A successful first pass should be able to:

1. Load ancient text plus metadata from a CSV or text file.
2. Run NER or entity extraction on each document.
3. Normalize entity names enough to connect obvious duplicates.
4. Build a graph with documents as nodes and extracted entities as linked neighbors.
5. Export a node/edge representation that can be inspected, filtered, and improved by hand.

The goal is to make entity linkage and document networks visible quickly, so a researcher can validate the extraction before investing in a more complex model.

## Key results so far

**Corpus scale:** 70,186 documents parsed, 44,930 dateable via HGV cross-reference (64%), spanning 400 BCE to 700+ CE.

**Temporal analysis:** The pipeline confirms known historical signals at decade-level resolution:
- **Constitutio Antoniniana (212 CE):** 25.7x increase in "Aurelius" frequency per document after 212 CE. The 210s decade spikes to 3.27 mentions/doc vs 0.016/doc pre-212.
- **Flavius displacement (330s–430s CE):** "Flavius" rises as a replacement gentilicium after Constantine, peaking at 1.18/doc in the 430s while Aurelius declines.
- **Phoibammon signal:** Christian-Coptic names appear only after ~400 CE, tracking Christianization independently.

**Geographic network:** 758 places connected by 20,934 edges (min 5 shared person names). Oxyrhynchos and the Arsinoites (Fayum) are the two dominant hubs — not Alexandria, which ranks only 12th in betweenness centrality. The Fayum is 76.7% insular: 25K of 33K person names appear only in Fayum documents. The remaining 7.7K names connect outward, primarily to Oxyrhynchos (2,660 shared), Hermopolis (1,288), and — surprisingly — Mons Claudianus, a remote Roman quarry in the Eastern Desert (285 shared), suggesting labor recruitment from the Fayum for imperial quarrying operations.

## Next steps

### Research directions

1. **Place-name normalization and spatial mapping.** The geographic network has known noise: "Arsinoites" and "Arsinoites, Ägypten" are separate nodes, as are "Philadelphia" / "Philadelphia?" / "Philadelphia (Arsinoites)". Linking to TM Geo IDs would collapse these and enable a proper geospatial visualization — a map of provincial Egypt's social connectivity, weighted by shared persons, layered by period. This work overlaps directly with Trismegistos collaboration (see below).

2. **Validation and error analysis.** The 64% dateability rate means 36% of documents lack HGV dates. Characterize what's missing — is it random, or are certain corpora/periods/regions systematically undated? Understanding the gaps strengthens any temporal or geographic claims built on the dated subset.

3. **Aurelius/Flavius crossover notebook.** Write up the temporal naming analysis as a standalone Jupyter notebook with inline plots. The Aurelius spike at 212 CE validates the pipeline; the Flavius displacement across the 4th–5th centuries and the exact crossover decade are the novel contribution. This is the reproducible demo for the community.

4. **Zenon Archive deep dive.** Merge Greek case forms in the graph (the stemmer handles this in entity resolution but not yet in graph construction), strip remaining place-name leaks, and produce a publication-quality social network of one person's 3rd-century BCE world.

5. **Greek morphological normalization.** The current stemmer handles major case endings (-ωνος → -ων, -αίου → -αῖος, etc.) but doesn't cover all declension patterns. A proper lemmatizer (e.g., CLTK's Greek module) would further reduce entity fragmentation.

