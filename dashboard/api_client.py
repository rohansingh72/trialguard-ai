from __future__ import annotations

from typing import Any

import requests


class TrialGuardAPIError(RuntimeError):
    pass


class TrialGuardAPI:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise TrialGuardAPIError(f"Could not reach TrialGuard API at {self.base_url}: {exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise TrialGuardAPIError(f"{response.status_code}: {detail}")

        if not response.content:
            return None
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def studies(self) -> list[dict[str, Any]]:
        return self._request("GET", "/studies").get("studies", [])

    def create_demo_study(self, name: str = "TrialGuard Demo Study") -> dict[str, Any]:
        return self._request("POST", "/studies/demo", params={"name": name})

    def summary(self, study_id: str) -> dict[str, Any]:
        return self._request("GET", f"/studies/{study_id}/summary")

    def subjects(self, study_id: str) -> list[str]:
        return self._request("GET", f"/studies/{study_id}/subjects").get("subjects", [])

    def sync_findings(self, study_id: str) -> dict[str, Any]:
        return self._request("POST", f"/studies/{study_id}/human-review/sync")

    def findings(self, study_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/studies/{study_id}/human-review/findings")

    def update_finding(
        self,
        study_id: str,
        finding_id: str,
        *,
        status: str,
        reviewer: str,
        note: str | None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/studies/{study_id}/human-review/findings/{finding_id}",
            json={"status": status, "reviewer": reviewer, "note": note or None},
        )

    def audit(self, study_id: str, finding_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/studies/{study_id}/human-review/findings/{finding_id}/audit",
        )

    def investigate(self, study_id: str, subject_id: str, question: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/studies/{study_id}/agent/investigate",
            json={"subject_id": subject_id, "question": question},
            timeout=max(self.timeout, 120.0),
        )
