"""Small pilot catalogue: primary-page cost review, never model-inferred pricing.

Re-review before expiry. Free content does not imply a free certificate.
"""
from datetime import date
import re

COURSES = [
    dict(title='Python for Everybody', provider='PY4E / Charles Severance', cost='Free',
         level='Beginner', duration='Self-paced', url='https://www.py4e.com/',
         why='Free lessons, book and assignments on the author’s site. Badges are available; this is not a promise of a university certificate.',
         topics=['python', 'programming'], reviewed_on='2026-09-28', expires_on='2026-10-28'),
    dict(title='Excel Skills for Business: Intermediate I', provider='Macquarie University / Coursera', cost='Paid',
         level='Intermediate', duration='Provider estimate: 3 weeks at 10 hours/week',
         url='https://www.coursera.org/learn/excel-intermediate-1',
         why='Paid certificate experience. A trial or financial aid is conditional, not a free full course. Check the local checkout price; Excel software may add cost.',
         topics=['excel', 'spreadsheet'], reviewed_on='2026-09-28', expires_on='2026-10-28'),
    dict(title='Talk the talk', provider='The Open University / OpenLearn', cost='Free',
         level='Beginner', duration='Provider estimate: 12 hours',
         url='https://www.open.edu/openlearn/education-development/talk-the-talk',
         why='Free presentation and speaking course with a free statement of participation after completion. An account is needed for the statement; it is not a degree or academic credit.',
         topics=['communication','presentation','presentations','speaking','speech'], reviewed_on='2026-09-28', expires_on='2026-10-28'),
    dict(title='Getting started with SPSS', provider='The Open University / OpenLearn', cost='Free',
         level='Beginner', duration='Provider estimate: 3 hours',
         url='https://www.open.edu/openlearn/society-politics-law/sociology/getting-started-spss/content-section-0',
         why='Free introductory statistics tutorial and statement of participation. Uses simulated activities, so buying SPSS is not required. Older interactive content may need a compatible browser; not academic credit.',
         topics=['spss','statistics','statistical','research','data'], reviewed_on='2026-09-28', expires_on='2026-10-28'),
    dict(title='Social science and participation', provider='The Open University / OpenLearn', cost='Free',
         level='Intermediate', duration='Provider estimate: 10 hours',
         url='https://www.open.edu/openlearn/society-politics-law/social-science-and-participation/content-section-6',
         why='Free course and statement of participation. Sign in to track completion; not academic credit. The page also advertises separate paid further study.',
         topics=['social','science','participation','society'], reviewed_on='2026-09-28', expires_on='2026-10-28'),

]


def reviewed_courses(interest, level, preference, today=None):
    today = today or date.today()
    words = set(re.findall(r'[a-z]+', interest.lower()))
    return [{k: v for k, v in c.items() if k not in ('topics', 'expires_on')}
            for c in COURSES if today <= date.fromisoformat(c['expires_on'])
            and words.intersection(c['topics']) and c['level'] == level
            and (preference == 'Free & Paid' or c['cost'] == preference.split()[0])]
