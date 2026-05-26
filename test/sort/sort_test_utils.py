def rank_indexed_u4(values, top_p=None):
    indexed = list(enumerate(values))
    ordered = sorted(indexed, key=lambda pair: (pair[1], pair[0]))
    ranked = [idx for idx, _ in ordered]
    if top_p is None:
        return ranked
    return ranked[:top_p]
