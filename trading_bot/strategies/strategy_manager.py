"""Strategy registry."""

from typing import Any, Dict, Type

from .base_strategy import BaseStrategy, Signal
from .ema_rsi_strategy import EMARsiStrategy

STRATEGIES: Dict[str, Type[BaseStrategy]] = {
    EMARsiStrategy.name: EMARsiStrategy,
}


def available_strategies():
    return {name: cls.display_name for name, cls in STRATEGIES.items()}


def get_strategy(name: str, **params) -> BaseStrategy:
    cls = STRATEGIES.get(name, EMARsiStrategy)
    return cls(**params)