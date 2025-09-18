"""Factory helpers for DoomArena adapter components."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

REAL_AVAILABLE = False

try:  # pragma: no cover - optional dependency
    from doomarena.attacks import EscalatingDialogueAttack as _RealEscalatingAttack
    from doomarena.filters import OutOfPolicyRefundFilter as _RealRefundFilter
except Exception:  # pragma: no cover - optional dependency
    _RealEscalatingAttack = None
    _RealRefundFilter = None
else:  # pragma: no cover - optional dependency
    REAL_AVAILABLE = True


@dataclass
class AdapterComponents:
    """Container for DoomArena adapter component constructors."""

    attack: Callable[..., Any]
    policy_filter: Callable[..., Any]
    mode: str


def _coerce_levels(levels: Optional[Iterable[Any]]) -> list[str]:
    if not levels:
        return []
    return [str(item) for item in levels]


def _make_shim_attack_factory(exp: str | None) -> Callable[..., Any]:
    from .attacks import EscalatingDialogueAttackAdapter

    def factory(**kwargs: Any) -> Any:
        levels = _coerce_levels(kwargs.get("levels"))
        return EscalatingDialogueAttackAdapter(levels=levels)

    return factory


def _make_shim_filter_factory(exp: str | None) -> Callable[..., Any]:
    from .filters import OutOfPolicyRefundFilter

    def factory(**kwargs: Any) -> Any:
        threshold = int(kwargs.get("threshold", 200))
        return OutOfPolicyRefundFilter(threshold=threshold)

    return factory


def _make_real_attack_factory(exp: str | None) -> Callable[..., Any]:  # pragma: no cover - optional dependency
    def factory(**kwargs: Any) -> Any:
        levels = _coerce_levels(kwargs.get("levels"))
        config: Dict[str, Any] = dict(kwargs.get("config") or {})

        attack_kwargs: Dict[str, Any] = {}
        if levels:
            attack_kwargs["levels"] = levels
        if config:
            attack_kwargs["config"] = config
        if exp:
            attack_kwargs.setdefault("exp", exp)

        attack = _RealEscalatingAttack(**attack_kwargs)  # type: ignore[misc]

        reset = getattr(attack, "reset", None)
        apply = getattr(attack, "apply", None)

        if callable(reset) and callable(apply):
            return attack

        class _AttackWrapper:
            def __init__(self, inner: Any) -> None:
                self._inner = inner
                self._reset = getattr(inner, "reset", None)
                self._call = getattr(inner, "apply", None) or getattr(inner, "__call__", None)

            def reset(self) -> None:
                if callable(self._reset):
                    self._reset()

            def apply(self, user_msg: str) -> str:
                if callable(self._call):
                    return self._call(user_msg)
                raise AttributeError("Attack object does not support apply()")

        return _AttackWrapper(attack)

    return factory


def _make_real_filter_factory(exp: str | None) -> Callable[..., Any]:  # pragma: no cover - optional dependency
    def factory(**kwargs: Any) -> Any:
        threshold = int(kwargs.get("threshold", 200))
        config: Dict[str, Any] = dict(kwargs.get("config") or {})

        filter_kwargs: Dict[str, Any] = {"threshold": threshold}
        if config:
            filter_kwargs["config"] = config
        if exp:
            filter_kwargs.setdefault("exp", exp)

        filter_obj = _RealRefundFilter(**filter_kwargs)  # type: ignore[misc]

        if callable(filter_obj):
            return filter_obj

        class _FilterWrapper:
            def __init__(self, inner: Any) -> None:
                self._inner = inner

            def __call__(self, *args: Any, **kw: Any) -> Any:
                call_method = getattr(self._inner, "__call__", None)
                if callable(call_method):
                    return call_method(*args, **kw)
                raise AttributeError("Filter object is not callable")

        return _FilterWrapper(filter_obj)

    return factory


def get_components(mode: str, exp: str | None = None) -> AdapterComponents:
    """Return constructor callables for the requested adapter mode."""

    requested = (mode or "SHIM").strip().upper()
    use_real = requested == "REAL" and REAL_AVAILABLE

    if requested == "REAL" and not REAL_AVAILABLE:
        print("[warn] REAL mode requested but DoomArena not available; falling back to SHIM.")

    if use_real:
        print("[info] Using REAL DoomArena adapters.")
        return AdapterComponents(
            attack=_make_real_attack_factory(exp),
            policy_filter=_make_real_filter_factory(exp),
            mode="REAL",
        )

    return AdapterComponents(
        attack=_make_shim_attack_factory(exp),
        policy_filter=_make_shim_filter_factory(exp),
        mode="SHIM",
    )
