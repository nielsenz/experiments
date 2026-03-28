# papyri-linkedin

Prototype workspace for ancient-text named entity extraction and relationship mapping.

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

**Zenon Archive case study:** 500 documents from the archive of Zenon of Philadelphia (~260–240 BCE) produce a genuine Ptolemaic social network. Zenon sits at degree 1,045 with contacts spanning Philadelphia, Alexandria, Memphis, and Palestine.

**Geographic coverage:** 1,931 unique place names across 68,839 geolocated documents. The Fayum oasis (Karanis, Tebtynis, Philadelphia, Theadelphia, Soknopaiou Nesos) accounts for ~12,000+ documents alone.

## Next steps

### Research directions

1. **Geographic network analysis.** We have 1,931 places across 68K documents. Build a spatial network: which places are connected by shared people? Do letter-writers in Oxyrhynchus correspond with the Fayum, or is the Fayum a self-contained social world? This is a map, not just a graph, and maps get attention.

2. **Aurelius/Flavius crossover notebook.** The Aurelius spike at 212 CE is textbook papyrology, but the *quantitative* demonstration of Flavius displacing Aurelius decade by decade across the 4th–5th centuries — and the exact crossover point — is not something that has been laid out this cleanly at this scale. Write this up as a standalone Jupyter notebook with inline plots. This is the calling card.

3. **Zenon Archive deep dive.** Clean up remaining noise (merge Greek case forms in the graph, strip last place-name leaks) and produce a publication-quality social graph of one man's 3rd-century BCE world. This is the most genuinely "LinkedIn-like" part of the whole corpus.

4. **Greek morphological normalization.** The current stemmer handles major case endings (-ωνος → -ων, -αίου → -αῖος, etc.) but doesn't cover all declension patterns. A proper lemmatizer (e.g., CLTK's Greek module) would further reduce fragmentation.

### Community engagement

5. **Contact papyri.info / Duke DC3.** Lead with the HGV cross-reference pipeline and the temporal validation results, not "we ran NLP on your data." The Aurelius/Flavius signals confirm what papyrologists already know — this builds trust before showing novel results. Josh Sosin at Duke is the PI for papyri.info.

6. **Contact Trismegistos (KU Leuven).** Mark Depauw's team would be interested in how TM IDs enabled the DDB–HGV enrichment at scale.

7. **Publish a reproducible notebook.** The digital papyrology community values reproducibility. A notebook that produces the Aurelius histogram from the idp.data corpus in 5 minutes is more compelling than a paper.

8. **Post to papy-l or present at a digital humanities venue.** The International Congress of Papyrology and DH conferences are natural fits.
