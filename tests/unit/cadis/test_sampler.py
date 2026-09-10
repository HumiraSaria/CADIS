"""Unit tests for the CADIS self-consistency sampler (mocked LLM, no live calls).

Covers the S5 sampler contract from newplan.md section 6: OpenRouter-only guard,
explicit temperature, per-call logging, retry/backoff, error reporting, and the
command extraction that feeds agreement.usc().
"""

from types import SimpleNamespace

import pytest

from pentestagent.cadis.sampler import (
    SelfConsistencySampler,
    _is_transient_error,
    canonical_action,
)
from pentestagent.cadis.signals import agreement

# --- fake provider responses --------------------------------------------------


def _resp_tool(name: str, args: str, tokens=(3, 5, 8)):
    fn = SimpleNamespace(name=name, arguments=args)
    tc = SimpleNamespace(function=fn)
    message = SimpleNamespace(content=None, tool_calls=[tc])
    choice = SimpleNamespace(message=message, finish_reason="tool_calls")
    usage = SimpleNamespace(
        prompt_tokens=tokens[0], completion_tokens=tokens[1], total_tokens=tokens[2]
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _resp_text(text: str):
    message = SimpleNamespace(content=text, tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    return SimpleNamespace(choices=[choice], usage=usage)


class RecordingFn:
    """A fake completion_fn that records kwargs and returns a fixed response."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


# --- canonical_action ---------------------------------------------------------


def test_canonical_action_tool_call_sorts_json_args():
    msg = _resp_tool("terminal", '{"b": 2, "a": 1}').choices[0].message
    assert canonical_action(msg) == 'terminal {"a": 1, "b": 2}'


def test_canonical_action_text_message():
    msg = _resp_text("just some reasoning").choices[0].message
    assert canonical_action(msg) == "just some reasoning"


# --- OpenRouter-only guard ----------------------------------------------------


def test_rejects_non_openrouter_model():
    with pytest.raises(ValueError):
        SelfConsistencySampler("gpt-4o")


def test_allows_non_openrouter_only_when_explicitly_disabled():
    # escape hatch for offline tests; production always requires openrouter/
    SelfConsistencySampler("gpt-4o", require_openrouter=False)


# --- N-sample batch + USC feed ------------------------------------------------


async def test_identical_samples_give_usc_zero():
    fn = RecordingFn(_resp_tool("terminal", '{"command": "nmap -sV t"}'))
    sampler = SelfConsistencySampler(
        "openrouter/anthropic/claude-3.5-sonnet", n_samples=5, completion_fn=fn
    )
    batch = await sampler.sample(messages=[{"role": "user", "content": "go"}])
    assert batch.n == 5 and batch.ok
    assert len(set(batch.commands)) == 1
    assert agreement.usc(batch.commands) == pytest.approx(0.0)
    assert batch.total_tokens() == 5 * 8


async def test_temperature_is_set_explicitly_even_for_anthropic_model():
    # The host LLM.generate() drops temperature for claude/anthropic; the sampler
    # must NOT -- verify T=0.7 reaches the completion fn.
    fn = RecordingFn(_resp_text("x"))
    sampler = SelfConsistencySampler(
        "openrouter/anthropic/claude-3.5-sonnet",
        n_samples=3,
        temperature=0.7,
        base_seed=100,
        completion_fn=fn,
    )
    await sampler.sample(messages=[{"role": "user", "content": "go"}])
    assert len(fn.calls) == 3
    assert all(c["temperature"] == 0.7 for c in fn.calls)
    # per-sample seeds propagate: base_seed + index
    assert sorted(c["seed"] for c in fn.calls) == [100, 101, 102]


# --- retry / backoff ----------------------------------------------------------


async def test_transient_error_is_retried(monkeypatch):
    import pentestagent.cadis.sampler as smod

    monkeypatch.setattr(smod.random, "uniform", lambda a, b: 0.0)
    state = {"n": 0}

    async def flaky(**kwargs):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("rate limit exceeded (429)")
        return _resp_text("ok")

    sampler = SelfConsistencySampler(
        "openrouter/x/y", n_samples=1, base_delay=0.0, completion_fn=flaky
    )
    batch = await sampler.sample(messages=[{"role": "user", "content": "go"}])
    assert batch.ok and batch.n == 1
    assert batch.calls[0].attempts == 2


async def test_nontransient_error_reported_not_ok():
    async def boom(**kwargs):
        raise ValueError("bad request 400")

    sampler = SelfConsistencySampler("openrouter/x/y", n_samples=2, completion_fn=boom)
    batch = await sampler.sample(messages=[{"role": "user", "content": "go"}])
    assert not batch.ok
    assert batch.commands == []  # nothing usable
    assert all(c.status == "error" for c in batch.calls)


# --- transient classification -------------------------------------------------


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Rate limit reached", True),
        ("HTTP 429 Too Many Requests", True),
        ("connection reset", True),
        ("503 Service Unavailable", True),
        ("400 invalid request", False),
        ("model not found", False),
    ],
)
def test_transient_classification(msg, expected):
    assert _is_transient_error(RuntimeError(msg)) is expected
