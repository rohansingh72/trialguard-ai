from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = {
    "DM": {"USUBJID", "BRTHDTC", "RFICDTC", "DMDISDTC"},
    "AE": {"USUBJID", "AEDECOD", "AESTDTC", "AEENDTC", "AETRTEMFL"},
    "LB": {"USUBJID", "LBTESTCD", "LBSTRESN", "LBSTRESU", "LBDTC"},
    "EX": {"USUBJID", "EXSTDTC", "EXDOSE"},
}

class TrialDataStore:
    def __init__(self) -> None:
        self.dm = pd.DataFrame(); self.ae = pd.DataFrame(); self.lb = pd.DataFrame(); self.ex = pd.DataFrame()

    def load_from_folder(self, folder: str | Path) -> None:
        folder = Path(folder)
        self.dm = pd.read_csv(folder / "DM.csv")
        self.ae = pd.read_csv(folder / "AE.csv")
        self.lb = pd.read_csv(folder / "LB.csv")
        self.ex = pd.read_csv(folder / "EX.csv")

    def load_frames(self, dm, ae, lb, ex) -> None:
        self.dm, self.ae, self.lb, self.ex = dm, ae, lb, ex

    def loaded(self) -> bool:
        return not self.dm.empty

    def all_subject_ids(self) -> list[str]:
        if self.dm.empty or "USUBJID" not in self.dm.columns: return []
        return sorted(self.dm["USUBJID"].dropna().astype(str).unique().tolist())

    def frames(self) -> dict[str, pd.DataFrame]:
        return {"DM": self.dm, "AE": self.ae, "LB": self.lb, "EX": self.ex}
