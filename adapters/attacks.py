from typing import List

class EscalatingDialogueAttackAdapter:
    """
    Minimal, DoomArena-shaped attack shim:
    - reset()     -> reset turn index
    - apply(msg)  -> return msg with the next escalation suffix appended
    """
    def __init__(self, levels: List[str] | None = None):
        self.levels: List[str] = levels or []
        self.i: int = 0

    def reset(self) -> None:
        self.i = 0

    def apply(self, user_msg: str) -> str:
        if not self.levels:
            return user_msg
        lvl = self.levels[min(self.i, len(self.levels) - 1)]
        self.i += 1
        return f"{user_msg} {lvl}"
