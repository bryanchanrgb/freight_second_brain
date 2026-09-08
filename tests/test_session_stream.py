import asyncio
import inspect

from freight_second_brain.agent.research import MAX_RECURSION, run_research_query
from freight_second_brain.agent.session import (
    ResearchDesk,
    ResearchSession,
    _chunk_text,
    _is_recursion_error,
)


def test_max_recursion_is_one_hundred() -> None:
    assert MAX_RECURSION == 100
    assert "MAX_RECURSION" in inspect.getsource(run_research_query)
    assert "MAX_RECURSION" in inspect.getsource(ResearchDesk.stream_turn)
    assert "recursion_limit" in inspect.getsource(ResearchDesk.stream_turn)


def test_chunk_text_extracts_reasoning() -> None:
    class Chunk:
        content = "visible"
        additional_kwargs = {"reasoning_content": "consider the horizon"}
        reasoning_content = None
        reasoning = None

    text, reasoning = _chunk_text(Chunk())
    assert text == "visible"
    assert "consider the horizon" in reasoning

    listed, thinking = _chunk_text(
        type("BlockChunk", (), {"content": [{"type": "reasoning", "text": "step one"}], "additional_kwargs": {}})()
    )
    assert listed == ""
    assert "step one" in thinking


def test_is_recursion_error() -> None:
    class GraphRecursionError(Exception):
        pass

    assert _is_recursion_error(GraphRecursionError("limit"))
    assert _is_recursion_error(RuntimeError("Recursion limit of 100 reached"))
    assert not _is_recursion_error(RuntimeError("network down"))


def test_stop_turn_cancels_in_flight_task(settings, monkeypatch) -> None:
    monkeypatch.setattr("freight_second_brain.agent.session.build_research_agent", lambda **_kwargs: object())
    desk = ResearchDesk(settings=settings)
    session = desk.create_session()

    async def run() -> None:
        async def sleeper() -> None:
            await asyncio.sleep(30)

        task = asyncio.create_task(sleeper())
        session.run_task = task
        result = desk.stop_turn(session.session_id)
        assert result["ok"] is True
        assert session.cancel_event.is_set()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()

    asyncio.run(run())


def test_session_cancel_event_defaults_clear() -> None:
    session = ResearchSession("s1")
    assert not session.cancel_event.is_set()
    assert session.run_task is None
