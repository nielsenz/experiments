from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    import spacy
except ImportError:  # pragma: no cover
    spacy = None


def load_documents(path: str):
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        if pd is None:
            raise ImportError("pandas is required to load CSV input")
        return pd.read_csv(file_path)
    text = file_path.read_text(encoding='utf-8')
    if pd is not None:
        return pd.DataFrame({"doc_id": [file_path.stem], "text": [text]})
    return [{"doc_id": file_path.stem, "text": text}]


def load_ner_model(model_name: str = "en_core_web_sm"):
    if spacy is None:
        return None
    try:
        return spacy.load(model_name)
    except Exception:
        return spacy.blank("en")


def extract_entities(text: str, nlp=None):
    if nlp is None:
        tokens = [token for token in text.split() if token.istitle()]
        return [(token.strip(".,;:"), "MISC") for token in tokens]
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in getattr(doc, "ents", [])]


def build_graph(records, nlp=None):
    graph = nx.Graph()
    for record in records:
        doc_id = str(record["doc_id"])
        text = str(record["text"])
        graph.add_node(doc_id, node_type="document")
        for entity_text, entity_label in extract_entities(text, nlp=nlp):
            entity_node = f"entity::{entity_text}"
            graph.add_node(entity_node, node_type="entity", label=entity_label)
            graph.add_edge(doc_id, entity_node, relation="mentions")
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NER over ancient text and build a simple graph.")
    parser.add_argument("input_path", help="CSV or text file containing papyrological material")
    parser.add_argument("--model", default="en_core_web_sm", help="spaCy model name to use when available")
    args = parser.parse_args()

    data = load_documents(args.input_path)
    nlp = load_ner_model(args.model)

    if hasattr(data, "to_dict"):
        records = data.to_dict(orient="records")
    else:
        records = data

    graph = build_graph(records, nlp=nlp)
    print(f"nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}")


if __name__ == "__main__":
    main()
