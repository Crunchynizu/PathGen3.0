from math import sqrt

from apps.feedback.retrieval.index import load_index


def cosine_similarity(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("Cosine similarity requires equal non-empty vectors.")
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def retrieve(query_embedding, top_k=4, min_similarity=0.35):
    if top_k <= 0:
        return []
    matches = []
    for chunk in load_index()["chunks"]:
        similarity = cosine_similarity(query_embedding, chunk["embedding"])
        if similarity >= min_similarity:
            match = dict(chunk)
            match["similarity"] = similarity
            matches.append(match)
    matches.sort(key=lambda match: (-match["similarity"], match["chunk_id"]))
    return matches[:top_k]
