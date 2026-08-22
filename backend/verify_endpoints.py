"""
Test matrix for the search & filter feature.
Covers all 14 cases from the acceptance criteria.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rakshak_project.settings')
django.setup()

from django.test import Client
import json

client = Client()

# Use seeded credentials: controller/admin123
logged_in = client.login(username='controller', password='admin123')
if not logged_in:
    print("WARNING: Could not log in — all tests will return 401/302")
else:
    print("Authenticated as: controller")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def check(label, condition, detail=""):
    marker = PASS if condition else FAIL
    print(f"  [{marker}] {label}" + (f" — {detail}" if detail else ""))
    return condition

results = []

print("\n" + "="*60)
print("TEST MATRIX: Search & Filter Feature")
print("="*60)

# ----------------------------------------------------------------
# 1. Search only
# ----------------------------------------------------------------
print("\nTest 1: Search only (search=bearing)")
r = client.get('/tickets/api/search/?search=bearing')
d = r.json()
t1a = check("Status 200", r.status_code == 200)
t1b = check("Returns tickets", d.get('total', 0) > 0, f"total={d.get('total')}")
t1c = check("All results contain 'bearing'", all(
    'bearing' in t.get('issue_raw','').lower() or
    'bearing' in t.get('description','').lower() or
    'bearing' in t.get('section_raw','').lower()
    for t in d.get('tickets', [])
), f"total={d.get('total')}")
results.extend([t1a, t1b, t1c])

# ----------------------------------------------------------------
# 2. Section filter only
# ----------------------------------------------------------------
print("\nTest 2: Section filter only")
sections = d.get('filters', {}).get('sections', [])
if sections:
    test_section = sections[0]
    r2 = client.get(f'/tickets/api/search/?section={test_section}')
    d2 = r2.json()
    t2a = check("Status 200", r2.status_code == 200)
    t2b = check("All results in correct section", all(
        t.get('track_id') == test_section for t in d2.get('tickets', [])
    ), f"section={test_section}, total={d2.get('total')}")
    results.extend([t2a, t2b])
else:
    print("  [SKIP] No sections in filters")

# ----------------------------------------------------------------
# 3. Status filter only
# ----------------------------------------------------------------
print("\nTest 3: Status filter only (status=open)")
r3 = client.get('/tickets/api/search/?status=open')
d3 = r3.json()
t3a = check("Status 200", r3.status_code == 200)
t3b = check("All results have status=open", all(
    t.get('status') == 'open' for t in d3.get('tickets', [])
), f"total={d3.get('total')}")
t3c = check("Returns >0 results", d3.get('total', 0) > 0)
results.extend([t3a, t3b, t3c])

# ----------------------------------------------------------------
# 4. Agent/team filter only
# ----------------------------------------------------------------
print("\nTest 4: Team/agent filter only")
teams = client.get('/tickets/api/search/').json().get('filters', {}).get('teams', [])
if teams:
    test_team = teams[0]
    r4 = client.get(f'/tickets/api/search/?team={test_team}')
    d4 = r4.json()
    t4a = check("Status 200", r4.status_code == 200)
    t4b = check("All results have correct team", all(
        t.get('team_raw') == test_team for t in d4.get('tickets', [])
    ), f"team={test_team}, total={d4.get('total')}")
    results.extend([t4a, t4b])

# ----------------------------------------------------------------
# 5. Missing data filter only
# ----------------------------------------------------------------
print("\nTest 5: Missing data filter only (missing_data=true)")
r5 = client.get('/tickets/api/search/?missing_data=true')
d5 = r5.json()
t5a = check("Status 200", r5.status_code == 200)
t5b = check("Returns tickets with missing data", d5.get('total', 0) > 0, f"total={d5.get('total')}")
t5c = check("All results have has_missing_data=true", all(
    t.get('has_missing_data') == True for t in d5.get('tickets', [])
))
results.extend([t5a, t5b, t5c])

print("\nTest 5b: Missing data filter (missing_data=false)")
r5b = client.get('/tickets/api/search/?missing_data=false')
d5b = r5b.json()
t5d = check("All results have has_missing_data=false", all(
    t.get('has_missing_data') == False for t in d5b.get('tickets', [])
), f"total={d5b.get('total')}")
results.append(t5d)

# ----------------------------------------------------------------
# 6. Search + section combined
# ----------------------------------------------------------------
print("\nTest 6: Search + section combined")
r6 = client.get('/tickets/api/search/?search=bearing&section=TRK-ADI-BRC-145')
d6 = r6.json()
t6a = check("Status 200", r6.status_code == 200)
t6b = check("Only correct section returned", all(
    t.get('track_id') == 'TRK-ADI-BRC-145' for t in d6.get('tickets', [])
), f"total={d6.get('total')}")
results.extend([t6a, t6b])

# ----------------------------------------------------------------
# 7. Search + status combined
# ----------------------------------------------------------------
print("\nTest 7: Search + status combined (bearing + open)")
r7 = client.get('/tickets/api/search/?search=bearing&status=open')
d7 = r7.json()
t7a = check("Status 200", r7.status_code == 200)
t7b = check("All results are open", all(
    t.get('status') == 'open' for t in d7.get('tickets', [])
), f"total={d7.get('total')}")
results.extend([t7a, t7b])

# ----------------------------------------------------------------
# 8. Search + missing_data combined
# ----------------------------------------------------------------
print("\nTest 8: Search + missing_data combined (inspection + missing=true)")
r8 = client.get('/tickets/api/search/?search=inspection&missing_data=true')
d8 = r8.json()
t8a = check("Status 200", r8.status_code == 200)
t8b = check("All results have missing data", all(
    t.get('has_missing_data') == True for t in d8.get('tickets', [])
), f"total={d8.get('total')}")
results.extend([t8a, t8b])

# ----------------------------------------------------------------
# 9. Multiple filters simultaneously
# ----------------------------------------------------------------
print("\nTest 9: status=open + missing_data=true + search=bearing")
r9 = client.get('/tickets/api/search/?search=bearing&status=open&missing_data=true')
d9 = r9.json()
t9a = check("Status 200", r9.status_code == 200)
t9b = check("All results: open AND missing data", all(
    t.get('status') == 'open' and t.get('has_missing_data')
    for t in d9.get('tickets', [])
), f"total={d9.get('total')}")
results.extend([t9a, t9b])

# ----------------------------------------------------------------
# 10. Reset (no filters)
# ----------------------------------------------------------------
print("\nTest 10: No filters (reset state) returns all tickets")
r10 = client.get('/tickets/api/search/')
d10 = r10.json()
t10a = check("Status 200", r10.status_code == 200)
t10b = check("Returns all 1020+ tickets", d10.get('total', 0) >= 1000, f"total={d10.get('total')}")
t10c = check("filters block present", 'filters' in d10)
results.extend([t10a, t10b, t10c])

# ----------------------------------------------------------------
# 11. No-result state
# ----------------------------------------------------------------
print("\nTest 11: No-result state (search=XYZZY_NONEXISTENT_KEYWORD)")
r11 = client.get('/tickets/api/search/?search=XYZZY_NONEXISTENT_KEYWORD_99999')
d11 = r11.json()
t11a = check("Status 200", r11.status_code == 200)
t11b = check("Returns 0 tickets", d11.get('total') == 0, f"total={d11.get('total')}")
t11c = check("tickets list is empty", d11.get('tickets') == [])
results.extend([t11a, t11b, t11c])

# ----------------------------------------------------------------
# 12. Invalid filter value
# ----------------------------------------------------------------
print("\nTest 12: Invalid status value")
r12 = client.get('/tickets/api/search/?status=INVALID_STATUS')
t12 = check("Returns 400", r12.status_code == 400, f"status={r12.status_code}")
results.append(t12)

# ----------------------------------------------------------------
# 13. Existing ticket page still works
# ----------------------------------------------------------------
print("\nTest 13: Existing tickets HTML page still loads")
r13 = client.get('/tickets/')
t13a = check("Status 200", r13.status_code == 200)
t13b = check("Contains ticket table", b'tickets-table' in r13.content)
t13c = check("Contains search input", b'ticket-search' in r13.content)
results.extend([t13a, t13b, t13c])

# ----------------------------------------------------------------
# 14. Existing checklist API still works
# ----------------------------------------------------------------
print("\nTest 14: Existing checklist update API unchanged")
from railway.models import Ticket
t = Ticket.objects.filter(ticket_code__startswith='DEMO-').first()
if t and t.source_checklist:
    item = t.source_checklist[0]
    from django.test import Client as C
    c14 = C()
    c14.login(username='controller', password='admin123')
    import json as _json
    r14 = c14.post(
        f'/tickets/api/{t.ticket_code}/update_checklist/',
        data=_json.dumps({'name': item['name'], 'completed': item.get('completed', False)}),
        content_type='application/json',
    )
    d14 = r14.json()
    t14a = check("Checklist API status 200", r14.status_code == 200)
    t14b = check("Checklist API success", d14.get('success') == True, str(d14))
    results.extend([t14a, t14b])
else:
    print("  [SKIP] No DEMO ticket with checklist found")

# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------
passed = sum(1 for r in results if r)
total  = len(results)
print(f"\n{'='*60}")
print(f"RESULT: {passed}/{total} checks passed")
if passed == total:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {total - passed}")
print("="*60)
