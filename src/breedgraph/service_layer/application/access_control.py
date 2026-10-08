from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections import defaultdict
from collections.abc import Iterable
from breedgraph.service_layer.tracking.wrappers import is_tracked_object

from breedgraph.domain.model.controls import (
    ControlledModel, ControlledAggregate, Controller, ReadRelease, Access, ControlledModelLabel
)
from breedgraph.domain.model.control_transfers import (
    ControlledEntity, ControlTransferInput, ControlTransferStored, ControlTransferStatus
)
from breedgraph.domain.events.control_transfers import ControlTransferOffered
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError, NoResultFoundError

from typing import Dict, List, Set, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamOrganisation:
    root_id: int
    legal_entity_declared: bool


class AbstractAccessControlService(ABC):
    """
    Service for managing controls over stored entities
    """
    user_id: int | None
    access_teams: Dict[Access, Set[int]]

    def __init__(self):
        self.events: List = []

    @staticmethod
    async def _parse_input_to_models_by_label(
            input_: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> Dict[ControlledModelLabel, Iterable[ControlledModel]]:
        controlled_models = []

        if isinstance(input_, Iterable) and not is_tracked_object(input_):
            # if is tracked object can still pass as an iterable then fail because it doesn't have an iter method
            # this is just because of object proxy so check is_tracked_object and revert to single element processing.
            for i in input_:
                if isinstance(i, ControlledAggregate):
                    controlled_models.extend(i.controlled_models)
                elif isinstance(i, ControlledModel):
                    controlled_models.append(i)
        else:
            if isinstance(input_, ControlledAggregate):
                controlled_models = input_.controlled_models
            elif isinstance(input_, ControlledModel):
                controlled_models = [input_]

        models_by_label: Dict[ControlledModelLabel, list[ControlledModel]] = {}
        for model in controlled_models:
            # exclude input models
            if not hasattr(model, 'id') or not model.id:
                continue

            if model.label not in models_by_label:
                models_by_label[model.label] = []
            models_by_label[model.label].append(model)
        return models_by_label

    async def set_controls(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate,
            control_teams: Set[int],
            release: ReadRelease
    ) -> None:
        """Set controls for all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""

        if not models:
            return

        models_by_label = await self._parse_input_to_models_by_label(models)
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._verify_and_set_controls(
                label=label,
                model_ids=model_ids,
                control_teams=control_teams,
                release=release
            )

    async def _verify_and_set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            control_teams: set[int],
            release: ReadRelease
    ):
        if not self.user_id:
            raise IllegalOperationError("User ID required to set controls")
        if not control_teams:
            raise IllegalOperationError("Control teams required to set controls")

        controllers = await self.get_controllers(label, model_ids)

        for model_id, controller in controllers.items():
            if not controller.has_access(Access.ADMIN, self.user_id, access_teams=control_teams):
                raise UnauthorisedOperationError("Admin access is required to set controls")

        # for models with existing controllers we need to filter out control teams provided that are not already in the controller.
        # this is per model so if we want to batch process we need to either split or do it in the query.
        await self._set_controls(
            label=label,
            model_ids=model_ids,
            team_ids=control_teams,
            release=release,
            user_id=self.user_id
        )

    async def set_controls_by_id_and_label(
            self,
            ids: Iterable[int],
            label: ControlledModelLabel,
            control_teams: Set[int],
            release: ReadRelease
    ):
        await self._verify_and_set_controls(label=label, model_ids=ids, control_teams=control_teams, release=release)

    @abstractmethod
    async def _set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        """Set controls for multiple entities - batch operation"""
        ...

    async def record_writes(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> None:
        """Record write stamp on all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""
        if not models:
            return

        if self.user_id is None:
            raise IllegalOperationError("User id required to record writes")

        models_by_label = await self._parse_input_to_models_by_label(models)

        # Create write stamps using batch operations
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._record_writes(
                label=label,
                model_ids=model_ids,
                user_id=self.user_id
            )

    @abstractmethod
    async def _record_writes(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            user_id: int
    ) -> None:
        """Record write stamps for multiple entities - batch operation"""
        ...

    async def get_controller(self, label: ControlledModelLabel, model_id: int) -> Optional[Controller]:
        """Get controller by label and model_id"""
        controllers = await self._get_controllers(label, [model_id])
        return controllers.get(model_id)

    async def get_controllers(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> Dict[int, Controller]:
        """
        Get multiple controllers by label and model_ids
        """
        return await self._get_controllers(label, model_ids)

    async def get_controllers_for_aggregate(self, aggregate: ControlledAggregate) -> Dict[ControlledModelLabel, Dict[int, Controller]]:
        """
        :param aggregate:
        :return: Dict keyed by label, the model_id to controller
        """
        label_model_ids = defaultdict(list)
        for model in aggregate.controlled_models:
            label_model_ids[model.label].append(model.id)
        controllers = {
            label: await self.get_controllers(label, model_ids)
            for label, model_ids in label_model_ids.items()
        }
        return controllers

    # Abstract methods for concrete implementations
    @abstractmethod
    async def _get_controllers(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> Dict[int, Controller]:
        """Get controllers for multiple model instances - key batch operation"""
        ...

    async def _verify_and_add_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Set[int],
            release: ReadRelease
    ) -> None:
        """
        Add control teams to existing models. Only called by the control transfer methods, which authorise the change.
        """
        if not self.user_id:
            raise IllegalOperationError("User ID required to add controls")
        if not team_ids:
            raise IllegalOperationError("Control teams required to add controls")

        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)
        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None:
                raise IllegalOperationError(f"No controls found for {label} {model_id}")
            if controller.teams.intersection(team_ids):
                raise IllegalOperationError(f"Teams already control {label} {model_id}")

        await self._add_controls(
            label=label,
            model_ids=model_ids,
            team_ids=team_ids,
            release=release,
            user_id=self.user_id
        )

    @abstractmethod
    async def _add_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        ...

    async def _verify_and_end_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Set[int]
    ) -> None:
        """
        End the control of teams over existing models. The ended controls are kept as history.
        At least one control team must remain for each model.
        Only called by the control transfer and renounce methods, which authorise the change.
        """
        if not self.user_id:
            raise IllegalOperationError("User ID required to end controls")
        if not team_ids:
            raise IllegalOperationError("Control teams required to end controls")

        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)
        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None:
                raise IllegalOperationError(f"No controls found for {label} {model_id}")
            if not team_ids.issubset(controller.teams):
                raise IllegalOperationError(f"Teams do not control {label} {model_id}")
            if not controller.teams - team_ids:
                raise IllegalOperationError(f"At least one control team must remain for {label} {model_id}")

        await self._end_controls(
            label=label,
            model_ids=model_ids,
            team_ids=team_ids,
            user_id=self.user_id
        )

    @abstractmethod
    async def _end_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            user_id: int
    ) -> None:
        ...

    # Control transfers, see docs/control-transfer.md
    @property
    def admin_teams(self) -> Set[int]:
        return set(self.access_teams.get(Access.ADMIN, set()))

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

    @staticmethod
    def _entity_ids_by_label(entities: Iterable[ControlledEntity]) -> Dict[ControlledModelLabel, List[int]]:
        ids_by_label = defaultdict(list)
        for entity in entities:
            ids_by_label[entity.label].append(entity.id)
        return ids_by_label

    async def _verify_entities_controlled_by(self, entities: Iterable[ControlledEntity], team_ids: Set[int]) -> None:
        for label, model_ids in self._entity_ids_by_label(entities).items():
            controllers = await self.get_controllers(label, model_ids)
            for model_id in model_ids:
                controller = controllers.get(model_id)
                if controller is None or not team_ids.issubset(controller.teams):
                    raise IllegalOperationError(f"Teams giving up control do not control {label} {model_id}")

    async def _get_recipient_teams(self, recipient_team: int) -> Set[int]:
        recipient_teams = await self._get_team_and_descendants(recipient_team)
        if not recipient_teams:
            raise NoResultFoundError(f"Recipient team {recipient_team} not found")
        return recipient_teams

    async def offer_transfer(
            self,
            entities: List[ControlledEntity],
            from_teams: Set[int],
            recipient_team: int,
            keep_from_teams: bool = False,
            to_teams: Set[int] | None = None,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> ControlTransferStored:
        """
        Offer control of entities to a recipient team.
        If the offering user is also an admin of the recipient team and to_teams are given, the transfer is accepted immediately.
        """
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to offer a control transfer")

        transfer_input = ControlTransferInput(
            entities=list(entities),
            from_teams=list(from_teams),
            recipient_team=recipient_team,
            keep_from_teams=keep_from_teams,
            offered_by=self.user_id
        )
        transfer_input.check_offer(admin_teams=self.admin_teams)
        await self._get_recipient_teams(recipient_team)
        await self._verify_entities_controlled_by(transfer_input.entities, set(transfer_input.from_teams))
        await self._verify_entity_rules(transfer_input)

        transfer = await self._create_transfer(transfer_input)

        if to_teams and recipient_team in self.admin_teams:
            return await self._accept_transfer(transfer, to_teams=to_teams, release=release)

        self.events.append(ControlTransferOffered(
            transfer_id=transfer.id,
            recipient_team=transfer.recipient_team,
            offered_by=transfer.offered_by,
            entity_count=len(transfer.entities)
        ))
        return transfer

    async def accept_transfer(
            self,
            transfer_id: int,
            to_teams: Set[int],
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> ControlTransferStored:
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to accept a control transfer")
        transfer = await self._require_transfer(transfer_id)
        return await self._accept_transfer(transfer, to_teams=to_teams, release=release)

    async def _accept_transfer(
            self,
            transfer: ControlTransferStored,
            to_teams: Set[int],
            release: ReadRelease
    ) -> ControlTransferStored:
        transfer.accept(
            agent_id=self.user_id,
            admin_teams=self.admin_teams,
            recipient_teams=await self._get_recipient_teams(transfer.recipient_team),
            to_teams=set(to_teams),
            release=release
        )
        await self._verify_entities_controlled_by(transfer.entities, set(transfer.from_teams))
        await self._verify_entity_rules(transfer)

        for label, model_ids in self._entity_ids_by_label(transfer.entities).items():
            controllers = await self.get_controllers(label, model_ids)
            for model_id in model_ids:
                # Teams taking control may already share control of some models
                teams_to_add = set(transfer.to_teams) - controllers[model_id].teams
                if teams_to_add:
                    await self._verify_and_add_controls(label, [model_id], teams_to_add, transfer.release)
            if transfer.teams_to_end:
                await self._verify_and_end_controls(label, model_ids, transfer.teams_to_end)
            await self._record_writes(label=label, model_ids=model_ids, user_id=self.user_id)

        return await self._set_transfer(transfer)

    async def _verify_entity_rules(self, transfer: ControlTransferInput | ControlTransferStored) -> None:
        """
        Rules for particular kinds of entity, checked at offer and at acceptance. See docs/control-transfer.md §5.
        Person: the organisation receiving control is the data controller, so it must have declared a legal entity,
        and a Person's control teams must stay within one organisation.
        """
        if not any(entity.label is ControlledModelLabel.PERSON for entity in transfer.entities):
            return

        recipient_organisation = await self._get_team_organisation(transfer.recipient_team)
        if recipient_organisation is None:
            raise NoResultFoundError(f"Recipient team {transfer.recipient_team} not found")
        if not recipient_organisation.legal_entity_declared:
            raise IllegalOperationError(
                "Persons can only be transferred to an organisation that has declared its legal entity"
            )
        if transfer.keep_from_teams:
            for team_id in transfer.from_teams:
                from_organisation = await self._get_team_organisation(team_id)
                if from_organisation is None or from_organisation.root_id != recipient_organisation.root_id:
                    raise IllegalOperationError(
                        "Control of a Person can only be shared between teams of the same organisation"
                    )

    async def reject_transfer(self, transfer_id: int) -> ControlTransferStored:
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to reject a control transfer")
        transfer = await self._require_transfer(transfer_id)
        transfer.reject(agent_id=self.user_id, admin_teams=self.admin_teams)
        return await self._set_transfer(transfer)

    async def cancel_transfer(self, transfer_id: int) -> ControlTransferStored:
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to cancel a control transfer")
        transfer = await self._require_transfer(transfer_id)
        transfer.cancel(agent_id=self.user_id, admin_teams=self.admin_teams)
        return await self._set_transfer(transfer)

    async def cancel_transfers_for_team(self, team_id: int) -> List[ControlTransferStored]:
        """Cancel pending transfers to or from a team that is being deleted."""
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to cancel control transfers")
        if team_id not in self.admin_teams:
            raise UnauthorisedOperationError("Admin access to the team is required to cancel its control transfers")

        pending = {
            transfer.id: transfer
            for transfer in await self._get_transfers(recipient_teams=[team_id], statuses=[ControlTransferStatus.PENDING])
        }
        pending.update({
            transfer.id: transfer
            for transfer in await self._get_transfers(from_teams=[team_id], statuses=[ControlTransferStatus.PENDING])
        })
        cancelled = []
        for transfer_id in sorted(pending):
            transfer = pending[transfer_id]
            transfer.cancel_for_deleted_team(agent_id=self.user_id, team_id=team_id)
            cancelled.append(await self._set_transfer(transfer))
        return cancelled

    async def renounce_controls(self, entities: List[ControlledEntity], team_ids: Set[int]) -> None:
        """
        End the control of teams over entities that other teams also control. Nobody gains control.
        """
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to renounce control")
        if not team_ids.issubset(self.admin_teams):
            raise UnauthorisedOperationError("Admin access to every renouncing team is required to renounce control")
        for label, model_ids in self._entity_ids_by_label(entities).items():
            await self._verify_and_end_controls(label, model_ids, team_ids)

    def _can_see_transfer(self, transfer: ControlTransferStored) -> bool:
        admin_teams = self.admin_teams
        return transfer.recipient_team in admin_teams or bool(admin_teams.intersection(transfer.from_teams))

    async def _require_transfer(self, transfer_id: int) -> ControlTransferStored:
        transfer = await self.get_transfer(transfer_id)
        if transfer is None:
            raise NoResultFoundError(f"Control transfer {transfer_id} not found")
        return transfer

    async def get_transfer(self, transfer_id: int) -> ControlTransferStored | None:
        """Transfers are visible to admins of the recipient team or of a team giving up control."""
        transfer = await self._get_transfer(transfer_id)
        if transfer is None or not self._can_see_transfer(transfer):
            return None
        return transfer

    async def get_transfers(
            self,
            statuses: Iterable[ControlTransferStatus] | None = None
    ) -> List[ControlTransferStored]:
        """Transfers offered to or from teams the user is an admin of."""
        admin_teams = self.admin_teams
        if not admin_teams:
            return []
        transfers = {
            transfer.id: transfer
            for transfer in await self._get_transfers(recipient_teams=admin_teams, statuses=statuses)
        }
        transfers.update({
            transfer.id: transfer
            for transfer in await self._get_transfers(from_teams=admin_teams, statuses=statuses)
        })
        return [transfers[transfer_id] for transfer_id in sorted(transfers)]

    @abstractmethod
    async def _get_team_organisation(self, team_id: int) -> TeamOrganisation | None:
        """The root of the team's organisation and whether it has declared a legal entity"""
        ...

    @abstractmethod
    async def _get_team_and_descendants(self, team_id: int) -> Set[int]:
        """The team and the teams below it, or an empty set if the team does not exist"""
        ...

    @abstractmethod
    async def _create_transfer(self, transfer: ControlTransferInput) -> ControlTransferStored:
        ...

    @abstractmethod
    async def _get_transfer(self, transfer_id: int) -> ControlTransferStored | None:
        ...

    @abstractmethod
    async def _get_transfers(
            self,
            recipient_teams: Iterable[int] | None = None,
            from_teams: Iterable[int] | None = None,
            statuses: Iterable[ControlTransferStatus] | None = None
    ) -> List[ControlTransferStored]:
        ...

    @abstractmethod
    async def _set_transfer(self, transfer: ControlTransferStored) -> ControlTransferStored:
        """Store the status and decision of a transfer, returning it with the recorded times"""
        ...
