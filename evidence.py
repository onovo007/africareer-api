"""Inspectable reference notes; these are NOT a full-document vector corpus.

Each note is a short paraphrase reviewed against the linked primary page.
Its hash covers the note, not the publisher's complete document. No confidence
probability is inferred from retrieval count, organisation or similarity score.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

CATALOG = Path(__file__).with_name('knowledge_sources.json')


def references(today=None):
    today = today or date.today()
    records = json.loads(CATALOG.read_text(encoding='utf-8'))
    return [dict(r, active=date.fromisoformat(r['review_due']) >= today)
            for r in records
            if hashlib.sha256(r['note'].encode()).hexdigest() == r['note_sha256']]


def select_references(query, limit=4):
    words = set(re.findall(r'\w+', query.lower()))
    ranked = []
    for r in references():
        if not r['active']:
            continue
        matches = words.intersection(r['tags'])
        # Institution-specific references must never be generalised to all schools.
        if r.get('requires_any') and not words.intersection(r['requires_any']):
            continue
        if matches:
            ranked.append((len(matches), r))
    return [r for _, r in sorted(ranked, key=lambda pair: (-pair[0], pair[1]['id']))[:limit]]


def reference_context(query):
    selected = select_references(query)
    texts, citations = [], []
    for r in selected:
        citation = f"{r['title']} — {r['section']} — {r['url']}"
        citations.append(citation)
        texts.append(f"SOURCE: {citation}\nREVIEWED PARAPHRASE (not original full text): {r['note']}\n"
                     f"SCOPE: {r['scope']}\nLIMITS: {r['limits']}\nReviewed: {r['reviewed_on']}")
    return '\n\n'.join(texts), citations


def evidence_status(sources, links=(), search_available=False):
    catalog = references()
    listed = []
    for citation in dict.fromkeys(sources):
        match = next((r for r in catalog if r['url'] in citation), None)
        listed.append({k: match[k] for k in ('title', 'url', 'scope', 'limits', 'reviewed_on', 'section')}
                      if match else {'title': citation, 'scope': 'Retrieved document excerpt',
                                     'limits': 'Review relevance and support for the individual claim.'})
    return {'status': 'references_supplied' if listed else 'general_guidance',
            'label': 'Reviewed references supplied' if listed else 'General guidance — no reviewed reference retrieved',
            'sources': listed, 'link_count': len(links), 'search_available': search_available,
            'claim_support': 'Not independently verified',
            'confidence_score': None,
            'explanation': 'This reports the evidence supplied to the AI, not a probability that its answer is correct. '
                           'References may support only part of an answer. Check personal recommendations and current requirements.'}
