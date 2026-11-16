from app.search import SHARED, Index, load_chunks, tokenize

index = Index(load_chunks())


def test_tokenize_drops_stopwords_and_case():
    assert tokenize("How do I reset the VPN?") == ["reset", "vpn"]


def test_finds_the_right_runbook():
    chunk, _ = index.search("VPN will not connect", "acme")
    assert chunk.id == "shared-002"


def test_unrelated_question_returns_nothing():
    assert index.search("best pizza topping in Naples", "acme") is None


def test_client_sees_own_and_shared_only():
    visible = {c.client for c in index.visible("acme")}
    assert visible == {"acme", SHARED}


def test_client_cannot_retrieve_other_clients_chunks():
    # Every chunk of every other client must be unreachable, whatever the question.
    for other in index.chunks:
        if other.client in ("acme", SHARED):
            continue
        hit = index.search(f"{other.title} {other.text}", "acme")
        assert hit is None or hit[0].client in ("acme", SHARED)


def test_hybrid_tenant_isolation():
    from app.ai import HybridRetriever

    retriever = HybridRetriever(index)
    for item in index.chunks:
        if item.client != "globex":
            continue
        hit = retriever.search(item.title + " " + item.text, "acme")
        assert hit is None or hit.chunk.client in ("acme", "shared")


def test_hybrid_typo_tolerance():
    from app.ai import HybridRetriever

    retriever = HybridRetriever(index)
    hit = retriever.search("VPN clent cannot conect gatewy", "acme")
    assert hit is not None and hit.chunk.id == "shared-002"
