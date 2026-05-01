"""Pipeline state machine definition.

Defines the PipelineState enum with 6 states and VALID_TRANSITIONS dict
that enforces the linear progression:
    PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE
with FAILED reachable from any non-terminal state.

The state machine is a custom Enum + frozenset implementation per D-14,
using no external library.
"""

from enum import StrEnum

from stockvaluefinder.utils.errors import StateTransitionError


class PipelineState(StrEnum):
    """Pipeline task state machine states.

    Linear progression: PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE.
    FAILED is reachable from any non-terminal state (PENDING, DOWNLOADING,
    PARSING, ANALYZING). DONE and FAILED are terminal states.
    """

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


VALID_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = {
    PipelineState.PENDING: frozenset({PipelineState.DOWNLOADING, PipelineState.FAILED}),
    PipelineState.DOWNLOADING: frozenset({PipelineState.PARSING, PipelineState.FAILED}),
    PipelineState.PARSING: frozenset({PipelineState.ANALYZING, PipelineState.FAILED}),
    PipelineState.ANALYZING: frozenset({PipelineState.DONE, PipelineState.FAILED}),
    PipelineState.DONE: frozenset(),
    PipelineState.FAILED: frozenset(),
}


def validate_transition(current: PipelineState, target: PipelineState) -> None:
    """Validate that a state transition is allowed.

    Args:
        current: The current pipeline state.
        target: The desired target state.

    Raises:
        StateTransitionError: If the transition is not valid.
    """
    if target not in VALID_TRANSITIONS[current]:
        raise StateTransitionError(current, target)


__all__ = ["PipelineState", "VALID_TRANSITIONS", "validate_transition"]
