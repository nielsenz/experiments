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
