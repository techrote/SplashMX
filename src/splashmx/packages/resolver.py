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


def resolve_packages(
    snapshot: CatalogSnapshot,
    roots: Sequence[DependencySpec],
    *,
    limits: SolverLimits | None = None,
) -> ResolutionLock:
    """Resolve authored ranges once and freeze an exact immutable runtime lock.

    Optional dependency solving is isolated from the required selection. A failing
    optional subtree uses only its declared fallback and cannot perturb an already
    coherent hard revision choice.
    """
    limits = limits or SolverLimits()
    index = _index(snapshot, limits)
    budget = _Budget()
    hard_roots = tuple(dep for dep in roots if dep.kind is not DependencyKind.OPTIONAL)
    selected, _ = _solve_hard(index, hard_roots, limits, budget)

    optional_selected: dict[PackageId, CatalogRow] = {}
    optional_roots = sorted((dep for dep in roots if dep.kind is DependencyKind.OPTIONAL), key=lambda dep: str(dep.package_id))
    for dep in optional_roots:
        if dep.package_id in selected:
            # Optional request cannot change a required revision. If the hard choice
            # does not satisfy it, the declared fallback wins.
            if not dep.requirement.matches(selected[dep.package_id].human_version):
                continue
            continue
        try:
            extension, _ = _solve_hard(index, (DependencySpec(dep.package_id, dep.requirement, DependencyKind.REQUIRED),), limits, budget, pinned={**selected, **optional_selected})
        except PackageError as exc:
            if exc.code == "package.version_conflict":
                continue
            raise
        for package_id, row in extension.items():
            if package_id not in selected:
                optional_selected[package_id] = row

    all_selected = {**selected, **optional_selected}
    if len(all_selected) > limits.max_packages:
        fail("package.package_count_limit", "resolved closure exceeds package bound")
    total_bytes = sum(row.bundle_size for row in all_selected.values())
    if total_bytes > limits.max_total_bytes:
        fail("package.total_byte_limit", "resolved closure exceeds package byte bound")

    # A package is lazy only when every incoming authored edge that selected it is lazy.
    lazy_ids = {dep.package_id for dep in roots if dep.kind is DependencyKind.LAZY}
    for row in all_selected.values():
        for child in row.dependencies:
            if child.kind is not DependencyKind.LAZY:
                lazy_ids.discard(child.package_id)
            elif child.package_id not in {d.package_id for d in row.dependencies if d.kind is not DependencyKind.LAZY}:
                lazy_ids.add(child.package_id)

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
