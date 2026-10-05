import hashlib

import pytest

from morpho.knowledge.documents import DOCUMENTS, get_document

# SHA-256 of each text as given in the challenge. A failure here means a document was edited,
# which the challenge forbids ("úsalos tal cual, no los edites").
EXPECTED_SHA256 = {
    "doc1": "520bee5c25d857e45f26b37920e187bcdcfc352a340d544f69c2cf27fa9bb1d5",
    "doc2": "2bf536892523a555c0bd80c574016013d9b83263167d3c88a36b9ef6f5394127",
    "doc3": "ddc9ccb886b1d8afbb01fc01a4da64796526b3912f46be5c2fa935d623275dd8",
    "doc4": "a52bf59082351ce3a8c609b48496743d54a0e9e68cec6e9ef91991742b574267",
    "doc5": "8285bffdfb65e2e9581d750a59d033d02357a7c8658fd88f2935d334b7e962c7",
}


def test_knowledge_base_has_the_five_policy_documents_in_order() -> None:
    assert [doc.doc_id for doc in DOCUMENTS] == ["doc1", "doc2", "doc3", "doc4", "doc5"]
    assert [doc.title for doc in DOCUMENTS] == [
        "Política de garantía",
        "Política de devoluciones",
        "Tiempos de envío",
        "Reembolsos",
        "Canales de contacto",
    ]


@pytest.mark.parametrize("doc_id", sorted(EXPECTED_SHA256))
def test_document_text_is_unchanged_from_the_challenge(doc_id: str) -> None:
    text = get_document(doc_id).text
    assert hashlib.sha256(text.encode()).hexdigest() == EXPECTED_SHA256[doc_id]


def test_unknown_document_id_raises() -> None:
    with pytest.raises(KeyError):
        get_document("doc6")
