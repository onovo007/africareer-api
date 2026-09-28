"""Conservative release gates, not a guarantee of factual correctness."""
import json
import re
from urllib.parse import urlparse


class DraftValidationError(ValueError):
    pass


def validate_cv_facts(cv, supplied):
    if not isinstance(cv, dict):
        raise DraftValidationError('The draft format could not be validated. Please retry.')
    text = json.dumps(cv, ensure_ascii=False)
    def numbers(value):
        return set(re.findall(r'(?<!\w)\d+(?:\.\d+)*(?:\s*%)?', value.replace(',', '')))
    if numbers(text) - numbers(supplied):
        raise DraftValidationError('The draft introduced unsupported numbers. No CV was downloaded. Please retry and review your supplied facts.')
    if re.search(r'\bnative\b', text, re.I) and not re.search(r'\bnative\b', supplied, re.I):
        raise DraftValidationError('The draft changed a language proficiency. No CV was downloaded. Please retry.')
    return cv


def primary_source(metadata):
    """Only reviewed original-document records qualify; legacy seeds do not."""
    url = str(metadata.get('source_url', ''))
    host = (urlparse(url).hostname or '').lower()
    allowed = ('unicef.org', 'ilo.org', 'unesco.org', 'afdb.org')
    valid_host = any(host == d or host.endswith('.' + d) for d in allowed)
    if not (url.startswith('https://') and valid_host and metadata.get('verified_primary') is True
            and metadata.get('title') and metadata.get('page')
            and re.fullmatch(r'[a-fA-F0-9]{64}', str(metadata.get('document_sha256', '')))):
        return None
    return f"{metadata['title']} — page {metadata['page']} — {url}"


def job_matches(result, role, location='', experience='', work_mode='', discipline=''):
    """Conservative text match; still not proof of an open vacancy or eligibility."""
    url = urlparse(result.get('url', ''))
    path = url.path.lower()
    if any(p in path for p in ('/search', '/pulse/', '/listing')) or path.endswith('-jobs.html'):
        return False
    if path.rstrip('/') in ('/jobs', '/jobs/remote', '/jobs/nairobi'):
        return False
    text = re.sub(r'[^a-z0-9]+', ' ', ' '.join(str(result.get(k, '')) for k in ('title', 'content')).lower())
    for criterion in (role, location, experience, work_mode, discipline):
        if not criterion or criterion.lower().startswith('any'):
            continue
        tokens = [t for t in re.findall(r'[a-z]+', criterion.lower()) if t not in ('and', 'or', 'in', 'the', 'years')]
        if not all(re.search(r'\b' + re.escape(t) + r'\b', text) for t in tokens):
            return False
    return True

# Snippet-based opportunity matching is intentionally conservative. Unknowns
# produce no match, rather than assigning a country from a domain suffix.
_REGION_TERMS={
 'Africa': 'africa nigeria ghana kenya uganda rwanda tanzania ethiopia senegal egypt morocco tunisia algeria zambia zimbabwe botswana namibia malawi mozambique cameroon south africa'.split(),
 'Europe': ['europe','united kingdom','uk','germany','france','spain','italy','switzerland','netherlands','sweden','norway','finland','denmark','ireland','portugal','austria','belgium','poland'],
 'Asia': ['asia','japan','china','india','singapore','malaysia','korea','taiwan','thailand','indonesia','hong kong'],
 'United States': ['united states','usa','u.s.','united states of america'],
}

def opportunity_matches(result, opp_type, field, region):
    text=' '.join(str(result.get(k,'')) for k in ('title','content')).lower()
    if not job_matches(result, field):
        return False
    types={'Scholarship':['scholarship','studentship','fellowship'],
           'PhD / Doctorate':['phd','ph.d','doctoral','doctorate'],
           'Undergraduate / Masters':['undergraduate','bachelor','master','msc','m.sc','bsc']}
    if not any(re.search(r'\b'+re.escape(t)+r'\b',text) for t in types.get(opp_type, [opp_type.lower()])):
        return False
    if re.search(r'\b(lecturer|faculty vacancy|postdoc|postdoctoral)\b',result.get('title',''),re.I):
        return False
    if region and region!='Other':
        if not any(re.search(r'\b'+re.escape(t)+r'\b',text) for t in _REGION_TERMS.get(region,[region.lower()])):
            return False
    return True
