# Minimal REAL client used by DoomArena-Lab.
# Starts with an "echo" provider (no external calls) to validate the REAL lane.
from __future__ import annotations
import os
import time
from dataclasses import dataclass

@dataclass
class RealClient:
    provider: str = "echo"
    model: str = "stub"
    api_key_env: str = "REAL_API_KEY"

    def _api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    def healthcheck(self) -> dict:
        # Return a small, serializable status blob for run.json.
        has_key = bool(self._api_key())
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "api_key_present": has_key,
            "ts": int(time.time()),
        }

    def generate(self, prompt: str) -> str:
        """
        For provider='echo', return the prompt back. This keeps the flow deterministic
        and exercises the REAL path without any external dependency.
        """
        if self.provider == "echo":
            return prompt
        # Placeholder for future providers (e.g., openai-compatible HTTP).
        raise NotImplementedError(f"Provider '{self.provider}' not implemented yet")
