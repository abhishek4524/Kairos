"""
test_hybrid_retrieval.py — Unit tests for Knowledge Graph layer and Hybrid Retrieval Engine.
"""

import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_store
from memory.hybrid_retrieval import retrieve_hybrid, _extract_query_entities


@pytest.fixture
def test_user():
    return f"user_kg_test_{uuid.uuid4().hex[:8]}"


def test_kg_storage_and_fact_upsert(test_user):
    fact_text = "Abhishek works on the Kairos project"
    entities = [
        {"name": "Abhishek", "type": "person"},
        {"name": "Kairos", "type": "project"},
    ]
    relations = [
        {"source": "Abhishek", "relation": "works_on", "target": "Kairos", "confidence": 0.95}
    ]

    fact_id = memory_store.upsert_fact(
        user_id=test_user,
        text=fact_text,
        source="test",
        entities=entities,
        relations=relations,
    )

    assert fact_id.startswith(f"fact_{test_user}_")

    # Check entities in SQLite
    all_ents = memory_store.get_all_entities(test_user)
    ent_names = [e["name"] for e in all_ents]
    assert "Abhishek" in ent_names
    assert "Kairos" in ent_names

    # Check relations in SQLite
    fact_rels = memory_store.get_relations_for_fact(fact_id)
    assert len(fact_rels) == 1
    assert fact_rels[0]["source"] == "Abhishek"
    assert fact_rels[0]["relation"] == "works_on"
    assert fact_rels[0]["target"] == "Kairos"

    # Check list_facts attached relations
    facts = memory_store.list_facts(test_user)
    assert len(facts) >= 1
    matching_fact = [f for f in facts if f["id"] == fact_id][0]
    assert len(matching_fact["relations"]) == 1
    assert matching_fact["relations"][0]["target"] == "Kairos"


def test_graph_neighborhood_traversal(test_user):
    # Setup 2-hop graph: Abhishek -> Kairos -> ChromaDB
    fact1 = "Abhishek's primary project is Kairos"
    fact2 = "Kairos relies on ChromaDB for local vector storage"

    fid1 = memory_store.upsert_fact(
        user_id=test_user,
        text=fact1,
        source="test",
        entities=[{"name": "Abhishek", "type": "person"}, {"name": "Kairos", "type": "project"}],
        relations=[{"source": "Abhishek", "relation": "works_on", "target": "Kairos", "confidence": 0.95}],
    )

    fid2 = memory_store.upsert_fact(
        user_id=test_user,
        text=fact2,
        source="test",
        entities=[{"name": "Kairos", "type": "project"}, {"name": "ChromaDB", "type": "tool"}],
        relations=[{"source": "Kairos", "relation": "uses", "target": "ChromaDB", "confidence": 0.95}],
    )

    # 1-hop traversal from Abhishek
    hop1 = memory_store.get_graph_neighborhood(test_user, ["Abhishek"], max_hops=1)
    assert len(hop1) == 1
    assert hop1[0]["target"] == "Kairos"

    # 2-hop traversal from Abhishek
    hop2 = memory_store.get_graph_neighborhood(test_user, ["Abhishek"], max_hops=2)
    assert len(hop2) == 2
    targets = [r["target"] for r in hop2]
    assert "Kairos" in targets
    assert "ChromaDB" in targets


def test_hybrid_retrieval_surfaces_graph_connected_facts(test_user):
    # Fact 1: Has direct semantic match for "project"
    fact1 = "Abhishek's primary project is Kairos"
    # Fact 2: Has no direct semantic match for "project I am working on", but is linked via Kairos
    fact2 = "Kairos relies on ChromaDB for local vector storage"

    memory_store.upsert_fact(
        user_id=test_user,
        text=fact1,
        source="test",
        entities=[{"name": "Abhishek", "type": "person"}, {"name": "Kairos", "type": "project"}],
        relations=[{"source": "Abhishek", "relation": "works_on", "target": "Kairos", "confidence": 0.95}],
    )

    memory_store.upsert_fact(
        user_id=test_user,
        text=fact2,
        source="test",
        entities=[{"name": "Kairos", "type": "project"}, {"name": "ChromaDB", "type": "tool"}],
        relations=[{"source": "Kairos", "relation": "uses", "target": "ChromaDB", "confidence": 0.95}],
    )

    query = "What database tools are used by the project Abhishek is working on?"
    context_str, scored_chunks = retrieve_hybrid(test_user, query, top_k=5)

    assert len(scored_chunks) >= 2
    chunk_previews = [c["preview"] for c in scored_chunks]

    # Verify Fact 2 (ChromaDB) is surfaced via graph connection
    assert any("ChromaDB" in p for p in chunk_previews)
    graph_chunks = [c for c in scored_chunks if c.get("is_graph_linked")]
    assert len(graph_chunks) >= 1


def test_extract_query_entities(test_user):
    memory_store.upsert_fact(
        user_id=test_user,
        text="Abhishek is building Kairos",
        entities=[{"name": "Abhishek", "type": "person"}, {"name": "Kairos", "type": "project"}],
        relations=[{"source": "Abhishek", "relation": "building", "target": "Kairos"}],
    )

    query = "Tell me about Abhishek and Kairos"
    extracted = _extract_query_entities(test_user, query)

    assert "Abhishek" in extracted or "abhishek" in [e.lower() for e in extracted]
    assert "Kairos" in extracted or "kairos" in [e.lower() for e in extracted]
