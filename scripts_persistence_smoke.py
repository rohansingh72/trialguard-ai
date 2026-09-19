from pathlib import Path
import tempfile

from app.services.persistent_review import PersistentHumanReviewStore
from app.services.study_repository import StudyRepository


with tempfile.TemporaryDirectory() as temp:
    repo = StudyRepository(Path(temp) / "trialguard")
    study = repo.create_from_folder(name="Persistence Smoke Study", folder="generated_data")
    trial = repo.load_store(study.study_id)

    reviews = PersistentHumanReviewStore(repo.db_path)
    created, total = reviews.sync_from_trial(study.study_id, trial)
    first = reviews.list_records(study.study_id)[0]
    reviews.update(
        study.study_id,
        first.finding_id,
        status="approved",
        reviewer="Smoke Tester",
        note="Persistence check.",
    )

    # Simulate an application restart by constructing entirely new repository objects.
    reopened_repo = StudyRepository(Path(temp) / "trialguard")
    reopened_reviews = PersistentHumanReviewStore(reopened_repo.db_path)
    restored = reopened_reviews.get(study.study_id, first.finding_id)

    print("Study ID:", study.study_id)
    print("Subjects after restart:", reopened_repo.load_store(study.study_id).all_subject_ids())
    print("Review findings created:", created, "/", total)
    print("Restored review status:", restored.status)
    print("Restored reviewer:", restored.reviewer)
    print("Audit events:", len(reopened_reviews.audit_events(study.study_id, first.finding_id)))
