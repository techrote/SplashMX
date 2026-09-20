"""Bounded deterministic package resolution for SMX-035.

This is deliberately a small PubGrub-family solver: it propagates accumulated
constraints, records incompatibilities, learns exact candidate bans when a choice
cannot satisfy its transitive closure, and deterministically backtracks. Runtime
code never invokes it; runtime consumes the resulting exact ResolutionLock.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .model import (
    CatalogRow, CatalogSnapshot, DependencyKind, DependencySpec, LockedPackage,
    PackageError, PackageId, PackageRevisionId, Requirement, ResolutionLock, fail,
)


@dataclass(frozen=True)
class SolverLimits:
    max_depth: int = 64
    max_packages: int = 512
    max_catalog_rows: int = 4096
    max_decisions: int = 10000
    max_total_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                fail("package.invalid_limit", f"{name} must be positive")


@dataclass(frozen=True)
class Incompatibility:
    package_id: PackageId
    requirements: tuple[str, ...]
    rejected_revision: PackageRevisionId | None
    reason: str


@dataclass
class _Budget:
    decisions: int = 0

    def tick(self, limits: SolverLimits) -> None:
        self.decisions += 1
        if self.decisions > limits.max_decisions:
            fail("package.solver_work_limit", "package resolution exceeded bounded solver work")


def _index(snapshot: CatalogSnapshot, limits: SolverLimits) -> dict[PackageId, list[CatalogRow]]:
    if len(snapshot.rows) > limits.max_catalog_rows:
        fail("package.catalog_row_limit", "catalog snapshot exceeds row bound")
    result: dict[PackageId, list[CatalogRow]] = {}
    for row in snapshot.rows:
        result.setdefault(row.package_id, []).append(row)
    for rows in result.values():
        rows.sort(key=lambda row: (row.human_version, str(row.package_revision_id)), reverse=True)
    return result


def _matching(rows: Sequence[CatalogRow], requirements: Sequence[Requirement], banned: set[PackageRevisionId]) -> list[CatalogRow]:
    return [
        row for row in rows
        if not row.revoked
        and row.package_revision_id not in banned
        and all(requirement.matches(row.human_version) for requirement in requirements)
    ]


def _solve_hard(
    index: Mapping[PackageId, Sequence[CatalogRow]],
    roots: Sequence[DependencySpec],
    limits: SolverLimits,
    budget: _Budget,
    *,
    pinned: Mapping[PackageId, CatalogRow] | None = None,
) -> tuple[dict[PackageId, CatalogRow], tuple[Incompatibility, ...]]:
    """Resolve required+lazy closure with learned exact-candidate incompatibilities."""
    constraints: dict[PackageId, list[Requirement]] = {}
    for dep in roots:
        if dep.kind is DependencyKind.OPTIONAL:
            continue
        constraints.setdefault(dep.package_id, []).append(dep.requirement)
    selected: dict[PackageId, CatalogRow] = dict(pinned or {})
    learned: dict[PackageId, set[PackageRevisionId]] = {}
    incompatibilities: list[Incompatibility] = []

    def recurse(
        current_constraints: dict[PackageId, list[Requirement]],
        current_selected: dict[PackageId, CatalogRow],
        depth: int,
    ) -> dict[PackageId, CatalogRow] | None:
        if depth > limits.max_depth:
            fail("package.dependency_depth_limit", "package dependency graph exceeds depth bound")
        if len(current_constraints) > limits.max_packages:
            fail("package.package_count_limit", "package closure exceeds package bound")
        budget.tick(limits)

        # Existing choices must continue to satisfy every newly propagated constraint.
        for package_id, row in current_selected.items():
            requirements = current_constraints.get(package_id, ())
            if requirements and not all(requirement.matches(row.human_version) for requirement in requirements):
                return None

        unresolved = sorted(
            (pid for pid in current_constraints if pid not in current_selected),
            key=str,
        )
        if not unresolved:
            return current_selected

        # Most-constrained first, deterministic PackageId tiebreak.
        package_id = min(
            unresolved,
            key=lambda pid: (len(_matching(index.get(pid, ()), current_constraints[pid], learned.get(pid, set()))), str(pid)),
        )
        requirements = current_constraints[package_id]
        candidates = _matching(index.get(package_id, ()), requirements, learned.get(package_id, set()))
        if not candidates:
            incompatibilities.append(Incompatibility(package_id, tuple(str(r) for r in requirements), None, "no compatible non-revoked revision"))
            return None

        for row in candidates:
            budget.tick(limits)
            candidate_selected = dict(current_selected)
            candidate_selected[package_id] = row
            candidate_constraints = {pid: list(reqs) for pid, reqs in current_constraints.items()}
            valid = True
            for child in row.dependencies:
                if child.kind is DependencyKind.OPTIONAL:
                    continue
                candidate_constraints.setdefault(child.package_id, []).append(child.requirement)
                already = candidate_selected.get(child.package_id)
                if already is not None and not child.requirement.matches(already.human_version):
                    valid = False
                    break
            if valid:
                answer = recurse(candidate_constraints, candidate_selected, depth + 1)
                if answer is not None:
                    return answer
            learned.setdefault(package_id, set()).add(row.package_revision_id)
            incompatibilities.append(
                Incompatibility(package_id, tuple(str(r) for r in requirements), row.package_revision_id, "candidate transitive closure is incompatible")
            )
        return None

    answer = recurse(constraints, selected, 0)
    if answer is None:
        detail = incompatibilities[-1].reason if incompatibilities else "unsatisfied constraints"
        raise PackageError("package.version_conflict", f"no coherent exact package closure: {detail}")
    return answer, tuple(incompatibilities)


def _optional_dependencies(rows: Sequence[CatalogRow]) -> list[DependencySpec]:
    dependencies: list[DependencySpec] = []
    for row in sorted(rows, key=lambda candidate: (str(candidate.package_id), str(candidate.package_revision_id))):
        dependencies.extend(
            sorted(
                (dep for dep in row.dependencies if dep.kind is DependencyKind.OPTIONAL),
                key=lambda dep: (str(dep.package_id), str(dep.requirement), dep.fallback or ""),
            )
        )
    return dependencies


def resolve_packages(
    snapshot: CatalogSnapshot,
    roots: Sequence[DependencySpec],
    *,
    limits: SolverLimits | None = None,
) -> ResolutionLock:
    """Resolve authored ranges once and freeze an exact immutable runtime lock.

    Optional dependency solving is isolated from the required selection. Optional
    edges declared by roots *or selected package manifests* are considered in stable
    order. A failing optional subtree uses only its declared fallback and cannot
    perturb an already coherent hard revision choice.
    """
    limits = limits or SolverLimits()
    index = _index(snapshot, limits)
    budget = _Budget()
    hard_roots = tuple(dep for dep in roots if dep.kind is not DependencyKind.OPTIONAL)
    selected, _ = _solve_hard(index, hard_roots, limits, budget)

    all_selected: dict[PackageId, CatalogRow] = dict(selected)
    optional_queue = sorted(
        (dep for dep in roots if dep.kind is DependencyKind.OPTIONAL),
        key=lambda dep: (str(dep.package_id), str(dep.requirement), dep.fallback or ""),
    )
    optional_queue.extend(_optional_dependencies(tuple(all_selected.values())))
    queued_row_revisions = {row.package_revision_id for row in all_selected.values()}
    cursor = 0
    while cursor < len(optional_queue):
        dep = optional_queue[cursor]
        cursor += 1
        current = all_selected.get(dep.package_id)
        if current is not None:
            # An optional edge can use an already-selected compatible revision, but
            # it can never move an incompatible hard/earlier selection.
            continue
        try:
            extension, _ = _solve_hard(
                index,
                (DependencySpec(dep.package_id, dep.requirement, DependencyKind.REQUIRED),),
                limits,
                budget,
                pinned=all_selected,
            )
        except PackageError as exc:
            if exc.code == "package.version_conflict":
                continue
            raise
        new_rows: list[CatalogRow] = []
        for package_id, row in extension.items():
            if package_id in all_selected:
                continue
            all_selected[package_id] = row
            if row.package_revision_id not in queued_row_revisions:
                queued_row_revisions.add(row.package_revision_id)
                new_rows.append(row)
        optional_queue.extend(_optional_dependencies(tuple(new_rows)))

    if len(all_selected) > limits.max_packages:
        fail("package.package_count_limit", "resolved closure exceeds package bound")
    total_bytes = sum(row.bundle_size for row in all_selected.values())
    if total_bytes > limits.max_total_bytes:
        fail("package.total_byte_limit", "resolved closure exceeds package byte bound")

    # Lazy is a property of the complete selected graph, not traversal order. A
    # package may defer acquisition only if every selected incoming edge is lazy.
    incoming_kinds: dict[PackageId, list[DependencyKind]] = {package_id: [] for package_id in all_selected}
    for dep in roots:
        chosen = all_selected.get(dep.package_id)
        if chosen is not None and dep.requirement.matches(chosen.human_version):
            incoming_kinds[dep.package_id].append(dep.kind)
    for row in all_selected.values():
        for child in row.dependencies:
            chosen = all_selected.get(child.package_id)
            if chosen is not None and child.requirement.matches(chosen.human_version):
                incoming_kinds[child.package_id].append(child.kind)
    lazy_ids = {
        package_id
        for package_id, kinds in incoming_kinds.items()
        if kinds and all(kind is DependencyKind.LAZY for kind in kinds)
    }

    locked: dict[PackageId, LockedPackage] = {}
    for package_id, row in sorted(all_selected.items(), key=lambda item: str(item[0])):
        child_revisions = tuple(
            all_selected[dep.package_id].package_revision_id
            for dep in row.dependencies
            if dep.package_id in all_selected and dep.kind is not DependencyKind.OPTIONAL
        )
        locked[package_id] = LockedPackage(
            package_id, row.package_revision_id, row.human_version,
            row.bundle_digest, row.bundle_size, child_revisions,
            package_id in lazy_ids,
        )
    return ResolutionLock(snapshot.snapshot_id, locked)


__all__ = ["Incompatibility", "SolverLimits", "resolve_packages"]
