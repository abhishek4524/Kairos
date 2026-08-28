"""
test_reranker.py — Unit tests for RAG Reranker stage (CrossEncoder, LLM fallback, degradation).
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.reranker import rerank, _sigmoid, _rerank_llm, RERANKER_TOP_K


def test_sigmoid_normalization():
    assert 0.0 <= _sigmoid(5.0) <= 1.0
    assert 0.0 <= _sigmoid(-5.0) <= 1.0
    assert _sigmoid(0.0) == 0.5


def test_rerank_disabled_pass_through():
    candidates = [
        {"id": "1", "content": "chunk 1", "final_score": 0.9},
        {"id": "2", "content": "chunk 2", "final_score": 0.8},
        {"id": "3", "content": "chunk 3", "final_score": 0.7},
    ]

    with patch("memory.reranker.RERANKER_ENABLED", False):
        res = rerank("query", candidates, top_k=2)
        assert len(res) == 2
        assert res[0]["id"] == "1"
        assert res[1]["id"] == "2"


def test_cross_encoder_rerank_ordering():
    candidates = [
        {"id": "1", "content": "Generic unrelated text about apples", "final_score": 0.9},
        {"id": "2", "content": "Exact answer for FastAPI Python web backend", "final_score": 0.5},
        {"id": "3", "content": "Random text about weather", "final_score": 0.3},
    ]

    mock_model = MagicMock()
    # Predict high logit for item 2, lower logits for 1 and 3
    mock_model.predict.return_value = [1.0, 8.5, -2.0]

    with patch("memory.reranker._get_cross_encoder", return_value=mock_model), \
         patch("memory.reranker.RERANKER_MODE", "cross_encoder"):

        res = rerank("What web framework does Abhishek use?", candidates, top_k=2)
        assert len(res) == 2
        assert res[0]["id"] == "2"  # Exact answer promoted to Top-1
        assert "rerank_score" in res[0]
        assert res[0]["rerank_method"] == "cross_encoder"


def test_llm_rerank_fallback():
    candidates = [
        {"id": "c1", "content": "Irrelevant SQL info", "final_score": 0.8},
        {"id": "c2", "content": "Brave CDP remote debugging port 9222", "final_score": 0.4},
    ]

    mock_groq_resp = MagicMock()
    mock_groq_resp.choices[0].message.content = '{"1": 2, "2": 10}'

    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_resp

    with patch("groq.Groq", return_value=mock_groq_client), \
         patch.dict(os.environ, {"GROQ_API_KEY": "fake_key"}):

        res = _rerank_llm("Where is Brave CDP port configured?", candidates)
        assert len(res) == 2
        assert res[0]["id"] == "c2"  # Promoted by LLM score 10
        assert res[0]["rerank_score"] == 1.0


def test_graceful_degradation_when_cross_encoder_fails():
    candidates = [
        {"id": "1", "content": "Fact A", "final_score": 0.85},
        {"id": "2", "content": "Fact B", "final_score": 0.75},
    ]

    with patch("memory.reranker._get_cross_encoder", return_value=None), \
         patch("memory.reranker._rerank_llm", side_effect=RuntimeError("Groq unavailable")):

        res = rerank("query", candidates, top_k=2)
        assert len(res) == 2
        assert res[0]["id"] == "1"
        assert res[1]["id"] == "2"


def test_top_n_to_top_k_filtering():
    candidates = [{"id": f"c_{i}", "content": f"content {i}", "final_score": 0.9 - i*0.05} for i in range(15)]

    mock_model = MagicMock()
    mock_model.predict.return_value = [float(15 - i) for i in range(15)]

    with patch("memory.reranker._get_cross_encoder", return_value=mock_model):
        res = rerank("query", candidates, top_k=3)
        assert len(res) == 3
