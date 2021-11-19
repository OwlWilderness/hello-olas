# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This module contains the rounds for the APY estimation ABCI application."""
from abc import ABC
from types import MappingProxyType
from typing import AbstractSet, Dict, Mapping, Optional, Tuple, Type, cast

import pandas as pd

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    BasePeriodState,
    CollectDifferentUntilThresholdRound,
    EventType,
    TransactionType,
)
from packages.valory.skills.apy_estimation.payloads import TransformationPayload
from packages.valory.skills.apy_estimation.tools import transform
from packages.valory.skills.price_estimation_abci.payloads import (
    EstimatePayload,
    ObservationPayload,
    RandomnessPayload,
    SelectKeeperPayload,
    SignaturePayload,
    TransactionHashPayload,
    ValidatePayload,
)
from packages.valory.skills.price_estimation_abci.rounds import (
    CollectSignatureRound,
    DeployOracleRound,
    DeploySafeRound,
    EstimateConsensusRound,
    Event,
    FinalizationRound,
)
from packages.valory.skills.price_estimation_abci.rounds import (
    PeriodState as PriceEstimationPeriodState,
)
from packages.valory.skills.price_estimation_abci.rounds import (
    RandomnessRound,
    ResetRound,
    SelectKeeperARound,
    SelectKeeperBRound,
    SelectKeeperBStartupRound,
    TxHashRound,
    ValidateOracleRound,
    ValidateSafeRound,
    ValidateTransactionRound,
)
from packages.valory.skills.simple_abci.rounds import (
    RandomnessStartupRound,
    RegistrationRound,
    ResetAndPauseRound,
    SelectKeeperAStartupRound,
)


class PeriodState(PriceEstimationPeriodState):
    """Class to represent a period state. This state is replicated by the tendermint application."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        participants: Optional[AbstractSet[str]] = None,
        period_count: Optional[int] = None,
        period_setup_params: Optional[Dict] = None,
        participant_to_randomness: Optional[Mapping[str, RandomnessPayload]] = None,
        most_voted_randomness: Optional[str] = None,
        participant_to_selection: Optional[Mapping[str, SelectKeeperPayload]] = None,
        most_voted_keeper_address: Optional[str] = None,
        safe_contract_address: Optional[str] = None,
        oracle_contract_address: Optional[str] = None,
        participant_to_votes: Optional[Mapping[str, ValidatePayload]] = None,
        participant_to_observations: Optional[Mapping[str, ObservationPayload]] = None,
        participant_to_transformation: Optional[
            Mapping[str, TransformationPayload]
        ] = None,
        participant_to_estimate: Optional[Mapping[str, EstimatePayload]] = None,
        transformation: Optional[pd.DataFrame] = None,
        estimate: Optional[float] = None,
        most_voted_estimate: Optional[float] = None,
        participant_to_tx_hash: Optional[Mapping[str, TransactionHashPayload]] = None,
        most_voted_tx_hash: Optional[str] = None,
        participant_to_signature: Optional[Mapping[str, SignaturePayload]] = None,
        final_tx_hash: Optional[str] = None,
    ) -> None:
        """Initialize the state."""
        super().__init__(
            participants,
            period_count,
            period_setup_params,
            participant_to_randomness,
            most_voted_randomness,
            participant_to_selection,
            most_voted_keeper_address,
            safe_contract_address,
            oracle_contract_address,
            participant_to_votes,
            participant_to_observations,
            participant_to_estimate,
            estimate,
            most_voted_estimate,
            participant_to_tx_hash,
            most_voted_tx_hash,
            participant_to_signature,
            final_tx_hash,
        )
        self._transformation = transformation
        self._participant_to_transformation = participant_to_transformation


class APYEstimationAbstractRound(AbstractRound[Event, TransactionType], ABC):
    """Abstract round for the price estimation skill."""

    @property
    def period_state(self) -> PeriodState:
        """Return the period state."""
        return cast(PeriodState, self._state)

    def _return_no_majority_event(self) -> Tuple[PeriodState, Event]:
        """
        Trigger the NO_MAJORITY event.

        :return: a new period state and a NO_MAJORITY event
        """
        return self.period_state, Event.NO_MAJORITY


class CollectObservationRound(
    CollectDifferentUntilThresholdRound, APYEstimationAbstractRound
):
    """
    This class represents the 'collect-observation' round.

    Input: a period state with the prior round data
    Output: a new period state with the prior round data and the observations

    It schedules the TransformRound.
    """

    round_id = "collect_observation"
    allowed_tx_type = ObservationPayload.transaction_type
    payload_attribute = "observation"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        # if reached observation threshold, set the result
        if self.collection_threshold_reached:
            observations = [
                getattr(payload, self.payload_attribute)
                for payload in self.collection.values()
            ]

            transformation = transform(observations)
            state = self.period_state.update(
                participant_to_observations=MappingProxyType(self.collection),
                transformation=transformation,
            )

            return state, Event.DONE

        return None


class TransformRound(CollectDifferentUntilThresholdRound, APYEstimationAbstractRound):
    """
    This class represents the 'Transform' round.

    Input: a period state with the prior round data
    Output: a new period state with the prior round data and the observations

    It schedules the EstimateConsensusRound.
    """

    def end_block(self) -> Optional[Tuple[BasePeriodState, EventType]]:
        """Process the end of the block."""
        raise NotImplementedError()


class APYEstimationAbciApp(AbciApp[Event]):  # pylint: disable=too-few-public-methods
    """APY estimation ABCI application."""

    initial_round_cls: Type[AbstractRound] = RegistrationRound
    transition_function: AbciAppTransitionFunction = {
        RegistrationRound: {
            Event.DONE: RandomnessStartupRound,
            Event.FAST_FORWARD: RandomnessRound,
        },
        RandomnessStartupRound: {
            Event.DONE: SelectKeeperAStartupRound,
            Event.ROUND_TIMEOUT: RandomnessStartupRound,  # if the round times out we restart
            # we can have some agents on either side of an epoch, so we retry
            Event.NO_MAJORITY: RandomnessStartupRound,
        },
        SelectKeeperAStartupRound: {
            Event.DONE: DeploySafeRound,
            Event.ROUND_TIMEOUT: RegistrationRound,  # if the round times out we restart
            Event.NO_MAJORITY: RegistrationRound,  # if the round has no majority we restart
        },
        DeploySafeRound: {
            Event.DONE: ValidateSafeRound,
            Event.DEPLOY_TIMEOUT: SelectKeeperAStartupRound,  # if the round times out we try with a new keeper
        },
        ValidateSafeRound: {
            Event.DONE: DeployOracleRound,
            Event.NEGATIVE: RegistrationRound,  # if the round does not reach a positive vote we restart
            Event.NONE: RegistrationRound,  # NOTE: unreachable
            Event.VALIDATE_TIMEOUT: RegistrationRound,
            # the tx validation logic has its own timeout, this is just a safety check
            Event.NO_MAJORITY: RegistrationRound,  # if the round has no majority we restart
        },
        DeployOracleRound: {
            Event.DONE: ValidateOracleRound,
            Event.DEPLOY_TIMEOUT: SelectKeeperBStartupRound,  # if the round times out we try with a new keeper
        },
        SelectKeeperBStartupRound: {
            Event.DONE: DeployOracleRound,
            Event.ROUND_TIMEOUT: RegistrationRound,  # if the round times out we restart
            Event.NO_MAJORITY: RegistrationRound,  # if the round has no majority we restart
        },
        ValidateOracleRound: {
            Event.DONE: RandomnessRound,
            Event.NEGATIVE: RegistrationRound,  # if the round does not reach a positive vote we restart
            Event.NONE: RegistrationRound,  # NOTE: unreachable
            Event.VALIDATE_TIMEOUT: RegistrationRound,
            # the tx validation logic has its own timeout, this is just a safety check
            Event.NO_MAJORITY: RegistrationRound,  # if the round has no majority we restart
        },
        RandomnessRound: {
            Event.DONE: SelectKeeperARound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: RandomnessRound,  # we can have some agents on either side of an epoch, so we retry
        },
        SelectKeeperARound: {
            Event.DONE: CollectObservationRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: ResetRound,  # if there is no majority we reset the period
        },
        CollectObservationRound: {
            Event.DONE: TransformRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
        },
        TransformRound: {
            Event.DONE: EstimateConsensusRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
        },
        EstimateConsensusRound: {
            Event.DONE: TxHashRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: ResetRound,  # if there is no majority we reset the period
        },
        TxHashRound: {
            Event.DONE: CollectSignatureRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: ResetRound,  # if there is no majority we reset the period
        },
        CollectSignatureRound: {
            Event.DONE: FinalizationRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: ResetRound,  # if there is no majority we reset the period
        },
        FinalizationRound: {
            Event.DONE: ValidateTransactionRound,
            Event.ROUND_TIMEOUT: SelectKeeperBRound,  # if the round times out we try with a new keeper
            Event.FAILED: SelectKeeperBRound,  # the keeper was unsuccessful
        },
        ValidateTransactionRound: {
            Event.DONE: ResetAndPauseRound,
            Event.NEGATIVE: ResetRound,  # if the round reaches a negative vote we continue
            Event.NONE: ResetRound,  # if the round reaches a none vote we continue
            # the tx validation logic has its own timeout, this is just a safety check
            Event.VALIDATE_TIMEOUT: ResetRound,
            # if there is no majority we re-run the round
            # (agents have different observations of the chain-state and need to agree before we can continue)
            Event.NO_MAJORITY: ValidateTransactionRound,
        },
        SelectKeeperBRound: {
            Event.DONE: FinalizationRound,
            Event.ROUND_TIMEOUT: ResetRound,  # if the round times out we reset the period
            Event.NO_MAJORITY: ResetRound,  # if there is no majority we reset the period
        },
        ResetRound: {
            Event.DONE: RandomnessRound,
            Event.ROUND_TIMEOUT: RegistrationRound,
            Event.NO_MAJORITY: RegistrationRound,
        },
        ResetAndPauseRound: {
            Event.DONE: RandomnessRound,
            Event.RESET_TIMEOUT: RegistrationRound,
            Event.NO_MAJORITY: RegistrationRound,
        },
    }
    event_to_timeout: Dict[Event, float] = {
        Event.ROUND_TIMEOUT: 30.0,
        Event.VALIDATE_TIMEOUT: 30.0,
        Event.DEPLOY_TIMEOUT: 30.0,
        Event.RESET_TIMEOUT: 30.0,
    }
