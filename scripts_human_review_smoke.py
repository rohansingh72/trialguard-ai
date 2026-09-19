from pathlib import Path

from app.services.data_store import TrialDataStore
from app.services.human_review import HumanReviewStore


store = TrialDataStore()
store.load_from_folder(Path("generated_data"))
reviews = HumanReviewStore()
created, total = reviews.sync_from_trial(store)

print(f"Created review records: {created}")
print(f"Total review records: {total}")

for record in reviews.list_records():
    print(
        f"{record.finding_id} | {record.finding.subject_id} | "
        f"{record.finding.rule_id} | {record.status}"
    )

first = reviews.list_records()[0]
updated = reviews.update(
    first.finding_id,
    status="needs_followup",
    reviewer="Demo Reviewer",
    note="Verify against source before closing.",
)

print("\nUpdated first finding:")
print(updated.model_dump_json(indent=2))

print("\nAudit trail:")
for event in reviews.audit_events(first.finding_id):
    print(event.model_dump_json(indent=2))
