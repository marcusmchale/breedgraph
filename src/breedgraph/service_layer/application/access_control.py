from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections import defaultdict
from collections.abc import Iterable
from breedgraph.service_layer.tracking.wrappers import is_tracked_object

from breedgraph.domain.model.controls import (
    ControlledModel, ControlledAggregate, Controller, ReadRelease, Access, ControlledModelLabel
)
from breedgraph.domain.model.control_transfers import (
    ControlledEntity, ControlScope, ControlTransferInput, ControlTransferStored, ControlTransferStatus
)
from breedgraph.domain.events.control_transfers import ControlTransferOffered
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError, NoResultFoundError

from typing import Dict, List, Set, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamTreeRoot:
    root_id: int


@dataclass(frozen=True)
class LicenceViolation:
    """
    A study whose licence is released less widely than the study, one of its datasets, or a file reference they or
    their records cite (docs/read-access.md, rule 10): the widest of the files, and one of them when the licence is
    released less widely than it
    """
    study_id: int
    licence_id: int
    licence_release: ReadRelease
    data_release: ReadRelease
    cited_release: ReadRelease | None = None
    cited_reference_id: int | None = None


# The widest release of some kinds of entity. Persons are never shown to anonymous users (docs/person.md §3)
RELEASE_CEILINGS: Dict[ControlledModelLabel, ReadRelease] = {
    ControlledModelLabel.PERSON: ReadRelease.REGISTERED
}

# The models whose releases decide whether a study's licence is released widely enough: the study, its datasets, the
# licence itself and the file references they cite
LICENCE_RULE_LABELS = frozenset({ControlledModelLabel.STUDY, ControlledModelLabel.DATASET, ControlledModelLabel.REFERENCE})


class AbstractAccessControlService(ABC):
    """
    Service for managing controls over stored entities
    """
    user_id: int | None
    access_teams: Dict[Access, Set[int]]

    def __init__(self):
        self.events: List = []
        # the models whose controls or links changed, by label, for require_released_licences
        self._licence_checks: Dict[ControlledModelLabel, Set[int]] = defaultdict(set)
        # the models created in this unit of work, by label: only these may take their first controls
        self._created: Dict[ControlledModelLabel, Set[int]] = defaultdict(set)

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

    async def note_created(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> None:
        """
        Note models as created in this unit of work, by the code that creates them, so that set_controls can give them
        their first controls. A stored model without controls is fixed, and can't be given any (Controller.fixed).
        """
        for label, label_models in (await self._parse_input_to_models_by_label(models)).items():
            self._created[label].update(model.id for model in label_models)

    async def set_controls(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate,
            control_teams: Set[int],
            release: ReadRelease
    ) -> None:
        """
        Set controls for all controlled models either supplied as a singleton, as a list or in an aggregate or list of
        aggregates. A model without controls takes its first ones only if noted as created in this unit of work
        (note_created); one with controls needs admin access.
        """

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

        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)

        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None or controller.fixed:
                if model_id not in self._created[label]:
                    raise IllegalOperationError(self._fixed_message(label, model_id))
            elif not controller.has_access(Access.ADMIN, self.user_id, access_teams=control_teams):
                raise UnauthorisedOperationError("Admin access is required to set controls")

        self._require_release_ceiling(label, release)
        await self._require_release_floor(label, model_ids, release)

        # A model whose controlling teams already have this release needs no new Control
        model_ids = [
            model_id for model_id in model_ids
            if not self._release_unchanged(controllers.get(model_id), control_teams, release)
        ]
        if not model_ids:
            return

        self.defer_licence_check(label, model_ids)
        # for models with existing controllers we need to filter out control teams provided that are not already in the controller.
        # this is per model so if we want to batch process we need to either split or do it in the query.
        await self._set_controls(
            label=label,
            model_ids=model_ids,
            team_ids=control_teams,
            release=release,
            user_id=self.user_id
        )

    @staticmethod
    def _release_unchanged(controller: Controller | None, control_teams: set[int], release: ReadRelease) -> bool:
        """Whether each of these teams that controls the model already has this release"""
        if controller is None:
            return False
        teams = control_teams & controller.teams
        return bool(teams) and all(controller.controls[team_id].release == release for team_id in teams)

    async def set_controls_by_id_and_label(
            self,
            ids: Iterable[int],
            label: ControlledModelLabel,
            control_teams: Set[int],
            release: ReadRelease
    ):
        """
        Set the release of stored entities by id (controlsSetRelease). Each must already be controlled: the admin
        check is on an entity's current controlling teams, and an entity without any would otherwise be taken over,
        with every team given, without a transfer. Creation gives entities their first controls through set_controls.
        """
        ids = list(ids)
        controllers = await self.get_controllers(label, ids)
        for model_id in ids:
            if controllers.get(model_id) is None or controllers[model_id].fixed:
                raise IllegalOperationError(self._fixed_message(label, model_id))
        await self._verify_and_set_controls(label=label, model_ids=ids, control_teams=control_teams, release=release)

    @staticmethod
    def _fixed_message(label: ControlledModelLabel, model_id: int) -> str:
        return f"{label.value} {model_id} has no controls, so no one can change it"

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

    async def record_writes_by_id(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> None:
        """Write stamps for models written outside their aggregate's repository, e.g. units' positions, by id"""
        model_ids = [model_id for model_id in dict.fromkeys(model_ids) if model_id is not None]
        if not model_ids:
            return
        if self.user_id is None:
            raise IllegalOperationError("User id required to record writes")
        await self._record_writes(label=label, model_ids=model_ids, user_id=self.user_id)

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

    async def require_access(self, label: ControlledModelLabel, model_ids: Iterable[int], access: Access) -> None:
        """
        For links and changes the repositories do not check: the user must have the given access to each model.
        A model the user cannot read is reported as not found. A fixed model, without controls, can be read by anyone
        and changed by no one.
        """
        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)
        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None or not controller.has_access(Access.READ, self.user_id, self.access_teams[Access.READ]):
                raise NoResultFoundError(f"{label.value} {model_id} was not found")
            if access is not Access.READ and controller.fixed:
                raise UnauthorisedOperationError(self._fixed_message(label, model_id))
            if not controller.has_access(access, self.user_id, self.access_teams[access]):
                raise UnauthorisedOperationError(f"This change requires {access.value.casefold()} access")

    @staticmethod
    def _require_release_ceiling(label: ControlledModelLabel, release: ReadRelease) -> None:
        ceiling = RELEASE_CEILINGS.get(label)
        if ceiling is not None and release > ceiling:
            raise IllegalOperationError(
                f"{label.plural} can be released at most to {ceiling.name.casefold()} users"
            )

    async def _require_release_floor(self, label: ControlledModelLabel, model_ids: Iterable[int], release: ReadRelease) -> None:
        """
        A reference's release cannot be lowered below the release of what cites it, so its controllers cannot hide
        a citation from those who can see what cites it (docs/contributions.md §6). The ontology counts as public.
        """
        if label != ControlledModelLabel.REFERENCE:
            return
        for reference_id, (public, citers) in (await self._get_reference_citers(list(model_ids))).items():
            floor = ReadRelease.PUBLIC if public else ReadRelease.PRIVATE
            for citer_label, citer_ids in citers.items():
                if floor == ReadRelease.PUBLIC:
                    break
                for controller in (await self.get_controllers(citer_label, list(citer_ids))).values():
                    floor = max(floor, controller.release)
            if release < floor:
                raise IllegalOperationError(
                    f"Reference {reference_id} is cited by data released as {floor.name}, so its release cannot be lower"
                )

    @abstractmethod
    async def _get_reference_citers(
            self, reference_ids: List[int]
    ) -> Dict[int, tuple[bool, Dict[ControlledModelLabel, Set[int]]]]:
        """For each reference: whether the ontology cites it, and the ids of the controlled models citing it by label"""
        ...

    def defer_licence_check(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> None:
        """
        Note models whose controls or links change, for require_released_licences to check as the unit of work
        commits. Every control change passes here; the repositories add the studies whose licence changes and the
        datasets moved to another study, and the dataset handlers the references a dataset or its records newly cite.
        """
        if label in LICENCE_RULE_LABELS:
            self._licence_checks[label].update(model_id for model_id in model_ids if model_id is not None)

    async def require_released_licences(self) -> None:
        """
        A study's licence is released at least as widely as the study, every dataset of the study and every file
        reference they or their records cite, so that whoever reads them by release can read the terms they are under
        rather than a placeholder, and accept them before downloading a file that holds the study's data
        (docs/read-access.md, rule 10; docs/licences.md §5). The rule spans several aggregates and every controlling
        team, so it is checked as the unit of work commits, on the releases that result, over the models noted by
        defer_licence_check. The refusal names the licence, and a file cited, never a study or dataset: the release of
        the data it is the licence of is at least registered, so every writer could see that much.
        """
        checks, self._licence_checks = self._licence_checks, defaultdict(set)
        if not checks:
            return
        violations = await self._get_licence_violations(
            study_ids=sorted(checks.get(ControlledModelLabel.STUDY, ())),
            dataset_ids=sorted(checks.get(ControlledModelLabel.DATASET, ())),
            reference_ids=sorted(checks.get(ControlledModelLabel.REFERENCE, ()))
        )
        if not violations:
            return
        violation = violations[0]
        files_wider = violation.cited_reference_id is not None
        if violation.licence_id in checks.get(ControlledModelLabel.REFERENCE, ()):
            if violation.licence_release < violation.data_release:
                raise IllegalOperationError(
                    f"Reference {violation.licence_id} is the licence of data released as {violation.data_release.name}, "
                    f"so its release cannot be lower"
                )
            raise IllegalOperationError(
                f"Reference {violation.licence_id} is the licence of data citing a file released as "
                f"{violation.cited_release.name}, so its release cannot be lower"
            )
        if files_wider and not violation.licence_release < violation.data_release:
            raise IllegalOperationError(
                f"Reference {violation.cited_reference_id}, released as {violation.cited_release.name}, is cited by data "
                f"under licence {violation.licence_id}, released as {violation.licence_release.name}: a licence is "
                f"released at least as widely as the files its data cites"
            )
        raise IllegalOperationError(
            f"Reference {violation.licence_id} is released as {violation.licence_release.name}, "
            f"so it cannot be the licence of data released as {violation.data_release.name}"
        )

    @abstractmethod
    async def _get_licence_violations(
            self, study_ids: List[int], dataset_ids: List[int], reference_ids: List[int]
    ) -> List[LicenceViolation]:
        """
        The studies among study_ids, those of the datasets dataset_ids, and those licensed by, or whose datasets or
        records cite, the references reference_ids, whose licence is released less widely than the study, one of its
        datasets or a file reference they or their records cite
        """
        ...

    async def require_read(self, label: ControlledModelLabel, model_ids: Iterable[int | None] | None) -> None:
        """
        For links to another aggregate, such as citing a reference: you can only link to what you can read.
        None ids are ignored, so optional links can be passed as they are.
        """
        model_ids = {model_id for model_id in model_ids or [] if model_id is not None}
        if model_ids:
            await self.require_access(label, model_ids, Access.READ)

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
            if controller is None or controller.fixed:
                raise IllegalOperationError(self._fixed_message(label, model_id))
            if controller.teams.intersection(team_ids):
                raise IllegalOperationError(f"Teams already control {label} {model_id}")

        self.defer_licence_check(label, model_ids)
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
            if controller is None or controller.fixed:
                raise IllegalOperationError(self._fixed_message(label, model_id))
            if not team_ids.issubset(controller.teams):
                raise IllegalOperationError(f"Teams do not control {label} {model_id}")
            if not controller.teams - team_ids:
                raise IllegalOperationError(f"At least one control team must remain for {label} {model_id}")

        # ending a control can widen the release that results, as the least of those that remain
        self.defer_licence_check(label, model_ids)
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
        await self._require_visible_recipient(recipient_team)
        await self._verify_entities_controlled_by(transfer_input.entities, set(transfer_input.from_teams))

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
        for label, model_ids in self._entity_ids_by_label(transfer.entities).items():
            self._require_release_ceiling(label, transfer.release)
            await self._require_release_floor(label, model_ids, transfer.release)

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

    async def _require_visible_recipient(self, recipient_team: int) -> None:
        """
        A transfer is offered to a team the offering user can see: a team tree root, which every signed-in user sees,
        or one of their own teams (docs/read-access.md, rule 9), as for affiliation requests. Hidden team ids are not
        probed, nor their admins sent offers.
        """
        if any(recipient_team in teams for teams in self.access_teams.values()):
            return
        team_tree = await self._get_team_tree(recipient_team)
        if team_tree is None or team_tree.root_id != recipient_team:
            raise NoResultFoundError(f"Recipient team {recipient_team} not found")

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

    async def get_scope_entities(self, scope: ControlScope) -> List[ControlledEntity]:
        """
        The entities a scope stands for: those of its label that its team currently controls, at its release when
        given, and for units only those at and below its units when given. Only for admins of the team.
        """
        if scope.team_id not in self.admin_teams:
            raise UnauthorisedOperationError("Admin access to the team is required to act on what it controls")
        if scope.below_unit_ids is not None and scope.label != ControlledModelLabel.UNIT:
            raise IllegalOperationError("Only a scope of units can be limited to the units below some units")
        return [ControlledEntity(label=scope.label, id=entity_id) for entity_id in await self._get_scope_entity_ids(scope)]

    async def entities_or_scope(
            self,
            entities: List[ControlledEntity] | None,
            scope: ControlScope | None
    ) -> List[ControlledEntity]:
        """The entities listed, or those a scope stands for: one or the other must be given"""
        if (entities is None) == (scope is None):
            raise IllegalOperationError("Give either the entities or a scope")
        return list(entities) if scope is None else await self.get_scope_entities(scope)

    @abstractmethod
    async def _get_scope_entity_ids(self, scope: ControlScope) -> List[int]:
        ...

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
    async def _get_team_tree(self, team_id: int) -> TeamTreeRoot | None:
        """The root of the team's team tree"""
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
