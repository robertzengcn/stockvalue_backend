"""Tests for PipelineState enum, VALID_TRANSITIONS, and validate_transition."""

import pytest

from stockvaluefinder.pipeline.state import (
    PipelineState,
    VALID_TRANSITIONS,
    validate_transition,
)
from stockvaluefinder.utils.errors import StateTransitionError


class TestPipelineStateMembers:
    """Test PipelineState has exactly 6 members."""

    def test_has_six_members(self) -> None:
        assert len(PipelineState) == 6

    def test_pending_exists(self) -> None:
        assert PipelineState.PENDING.value == "pending"

    def test_downloading_exists(self) -> None:
        assert PipelineState.DOWNLOADING.value == "downloading"

    def test_parsing_exists(self) -> None:
        assert PipelineState.PARSING.value == "parsing"

    def test_analyzing_exists(self) -> None:
        assert PipelineState.ANALYZING.value == "analyzing"

    def test_done_exists(self) -> None:
        assert PipelineState.DONE.value == "done"

    def test_failed_exists(self) -> None:
        assert PipelineState.FAILED.value == "failed"


class TestValidTransitions:
    """Test VALID_TRANSITIONS defines the correct state machine."""

    def test_pending_transitions(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.PENDING]
        assert valid == frozenset({PipelineState.DOWNLOADING, PipelineState.FAILED})

    def test_downloading_transitions(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.DOWNLOADING]
        assert valid == frozenset({PipelineState.PARSING, PipelineState.FAILED})

    def test_parsing_transitions(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.PARSING]
        assert valid == frozenset({PipelineState.ANALYZING, PipelineState.FAILED})

    def test_analyzing_transitions(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.ANALYZING]
        assert valid == frozenset({PipelineState.DONE, PipelineState.FAILED})

    def test_done_is_terminal(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.DONE]
        assert valid == frozenset()

    def test_failed_is_terminal(self) -> None:
        valid = VALID_TRANSITIONS[PipelineState.FAILED]
        assert valid == frozenset()


class TestValidateTransition:
    """Test validate_transition function."""

    def test_valid_pending_to_downloading(self) -> None:
        """Should complete without exception."""
        validate_transition(PipelineState.PENDING, PipelineState.DOWNLOADING)

    def test_valid_pending_to_failed(self) -> None:
        validate_transition(PipelineState.PENDING, PipelineState.FAILED)

    def test_valid_downloading_to_parsing(self) -> None:
        validate_transition(PipelineState.DOWNLOADING, PipelineState.PARSING)

    def test_valid_downloading_to_failed(self) -> None:
        validate_transition(PipelineState.DOWNLOADING, PipelineState.FAILED)

    def test_valid_parsing_to_analyzing(self) -> None:
        validate_transition(PipelineState.PARSING, PipelineState.ANALYZING)

    def test_valid_parsing_to_failed(self) -> None:
        validate_transition(PipelineState.PARSING, PipelineState.FAILED)

    def test_valid_analyzing_to_done(self) -> None:
        validate_transition(PipelineState.ANALYZING, PipelineState.DONE)

    def test_valid_analyzing_to_failed(self) -> None:
        validate_transition(PipelineState.ANALYZING, PipelineState.FAILED)

    def test_invalid_pending_to_parsing(self) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(PipelineState.PENDING, PipelineState.PARSING)
        assert "pending -> parsing" in exc_info.value.message

    def test_invalid_done_to_pending(self) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(PipelineState.DONE, PipelineState.PENDING)
        assert "done -> pending" in exc_info.value.message

    def test_invalid_failed_to_pending(self) -> None:
        with pytest.raises(StateTransitionError):
            validate_transition(PipelineState.FAILED, PipelineState.PENDING)

    def test_invalid_same_state(self) -> None:
        with pytest.raises(StateTransitionError):
            validate_transition(PipelineState.PENDING, PipelineState.PENDING)


class TestStateTransitionError:
    """Test StateTransitionError has correct message and details."""

    def test_message_format(self) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(PipelineState.PENDING, PipelineState.PARSING)
        assert exc_info.value.message == "Invalid state transition: pending -> parsing"

    def test_details_contain_current(self) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(PipelineState.PENDING, PipelineState.PARSING)
        assert exc_info.value.details["current"] == "pending"

    def test_details_contain_target(self) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(PipelineState.PENDING, PipelineState.PARSING)
        assert exc_info.value.details["target"] == "parsing"

    def test_extends_stockvaluefinder_error(self) -> None:
        error = StateTransitionError(PipelineState.PENDING, PipelineState.PARSING)
        from stockvaluefinder.utils.errors import StockValueFinderError

        assert isinstance(error, StockValueFinderError)
