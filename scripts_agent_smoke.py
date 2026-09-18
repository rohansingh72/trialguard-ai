from pathlib import Path

from app.agents.investigation import run_investigation
from app.services.data_store import TrialDataStore


store = TrialDataStore()
store.load_from_folder(Path("generated_data"))

result = run_investigation(
    store=store,
    subject_id="TG-001",
    question="Investigate this subject for possible data-quality issues.",
)

print("Review mode:", result.get("review_mode"))
print("Tools used:", result["tools_used"])
print("\nAnswer:\n")
print(result["answer"])

if "evidence" in result:
    print("\nDeterministic finding counts:")
    for tool_name, tool_result in result["evidence"]["qc"].items():
        print(f" - {tool_name}: {tool_result['finding_count']}")
