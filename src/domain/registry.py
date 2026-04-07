from typing import Callable

_policy_registry: dict[str, Callable] = {}
_assertion_registry: dict[str, Callable] = {}


def policy(name: str):
    def decorator(fn: Callable) -> Callable:
        _policy_registry[name] = fn
        return fn

    return decorator


def assertion(name: str):
    def decorator(fn: Callable) -> Callable:
        _assertion_registry[name] = fn
        return fn

    return decorator


def get_policy(name: str) -> Callable:
    if name not in _policy_registry:
        raise KeyError(f"Policy '{name}' not registered")
    return _policy_registry[name]


def get_assertion(name: str) -> Callable:
    if name not in _assertion_registry:
        raise KeyError(f"Assertion '{name}' not registered")
    return _assertion_registry[name]


def list_policies() -> list[str]:
    return list(_policy_registry.keys())


def list_assertions() -> list[str]:
    return list(_assertion_registry.keys())
