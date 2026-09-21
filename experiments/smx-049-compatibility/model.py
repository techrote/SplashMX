"""SMX-049 bounded compatibility/runtime-retention model.

This is decision-spike code, not a production loader.  It makes the selected
compatibility policy executable without redefining the production parsers owned
by SMX-024/035/036.  Architecture v1 remains authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Mapping


class CompatibilityError(ValueError):
    """Stable typed compatibility-programme outcome."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ArtifactClass(str, Enum):
    PROJECT = "canonical-project"
    PACKAGE = "package-component"
    CREATION = "creation-revision"
    WORLD_SAVE = "world-save"


class CompatibilityAction(str, Enum):
    DIRECT = "direct"
    MIGRATE = "migrate"
    RETAINED_RUNTIME = "retained-runtime"


@dataclass(frozen=True)
class GenerationRule:
    artifact_class: ArtifactClass
    generation: str
    action: CompatibilityAction
    target_generation: str | None = None
    runtime_profile: str | None = None
    migration_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.action is CompatibilityAction.MIGRATE:
            if not self.target_generation or not self.migration_steps:
                raise CompatibilityError(
                    "compatibility.invalid_policy",
                    "migration rules require an explicit target and bounded step chain",
                )
        elif self.migration_steps:
            raise CompatibilityError(
                "compatibility.invalid_policy",
                "non-migration rules cannot carry migration steps",
            )
        if self.action is CompatibilityAction.RETAINED_RUNTIME and not self.runtime_profile:
            raise CompatibilityError(
                "compatibility.invalid_policy",
                "retained-runtime rules require an exact runtime profile",
            )


@dataclass(frozen=True)
class CompatibilityDecision:
    artifact_class: ArtifactClass
    source_generation: str
    action: CompatibilityAction
    target_generation: str | None
    runtime_profile: str | None
    migration_steps: tuple[str, ...]


@dataclass(frozen=True)
class RetainedRuntime:
    profile: str
    digest: str
    size_bytes: int
    deployment_copies: int = 1

    def __post_init__(self) -> None:
        if not self.profile:
            raise CompatibilityError("compatibility.invalid_runtime", "runtime profile is required")
        if not self.digest.startswith("sha256:") or len(self.digest) != 71:
            raise CompatibilityError("compatibility.invalid_runtime", "runtime digest must be sha256:<64 hex>")
        try:
            int(self.digest[7:], 16)
        except ValueError as exc:
            raise CompatibilityError("compatibility.invalid_runtime", "runtime digest is not hexadecimal") from exc
        if self.size_bytes < 0 or self.deployment_copies < 1:
            raise CompatibilityError("compatibility.invalid_runtime", "runtime size/copy count is invalid")


BASELINE_RULES = (
    GenerationRule(
        ArtifactClass.PROJECT,
        "splashmx.project-revision/schema-0",
        CompatibilityAction.MIGRATE,
        target_generation="splashmx.project-revision/schema-1",
        migration_steps=("project-schema-0->1",),
    ),
    GenerationRule(
        ArtifactClass.PROJECT,
        "splashmx.project-revision/schema-1",
        CompatibilityAction.DIRECT,
    ),
    GenerationRule(
        ArtifactClass.PACKAGE,
        "splashmx.package-manifest/1+resolution-lock/1",
        CompatibilityAction.DIRECT,
    ),
    GenerationRule(
        ArtifactClass.CREATION,
        "splashmx.creation/1",
        CompatibilityAction.DIRECT,
        runtime_profile="splashmx.generic-player/1",
    ),
    GenerationRule(
        ArtifactClass.WORLD_SAVE,
        "splashmx.world-save/1",
        CompatibilityAction.DIRECT,
    ),
)


class CompatibilityProgramme:
    """Reference-based support policy for released SplashMX semantic generations.

    There is deliberately no implicit "last N versions" promise. A generation is
    supported only when it has an explicit rule and executable fixture. Removing
    one is therefore an explicit release-policy change rather than age-based GC.
    """

    def __init__(self, rules: Iterable[GenerationRule] = BASELINE_RULES, *, max_migration_steps: int = 8):
        self.max_migration_steps = max_migration_steps
        self._rules: dict[tuple[ArtifactClass, str], GenerationRule] = {}
        for rule in rules:
            key = (rule.artifact_class, rule.generation)
            if key in self._rules:
                raise CompatibilityError("compatibility.invalid_policy", f"duplicate generation rule {key}")
            if len(rule.migration_steps) > max_migration_steps:
                raise CompatibilityError("compatibility.migration_limit", "migration rule exceeds programme step bound")
            self._rules[key] = rule

    @property
    def rules(self) -> Mapping[tuple[ArtifactClass, str], GenerationRule]:
        return dict(self._rules)

    def negotiate(
        self,
        artifact_class: ArtifactClass,
        generation: str,
        *,
        required_features: Iterable[str] = (),
        supported_features: Iterable[str] = (),
        revoked: bool = False,
        runtime_available: bool = True,
    ) -> CompatibilityDecision:
        # Security/revocation always outranks historical compatibility. A retained
        # runtime is never an authority bypass for revoked bytes or trust roots.
        if revoked:
            raise CompatibilityError(
                "compatibility.revoked_artifact",
                "historical artifact/runtime is revoked by current security policy",
            )
        unknown = set(required_features) - set(supported_features)
        if unknown:
            raise CompatibilityError(
                "compatibility.unsupported_required_semantics",
                f"unsupported required semantics: {sorted(unknown)}",
            )
        rule = self._rules.get((artifact_class, generation))
        if rule is None:
            raise CompatibilityError(
                "compatibility.unsupported_generation",
                f"no supported compatibility rule for {artifact_class.value} generation {generation}",
            )
        if rule.action is CompatibilityAction.RETAINED_RUNTIME and not runtime_available:
            raise CompatibilityError(
                "compatibility.runtime_unavailable",
                f"required retained runtime {rule.runtime_profile} is unavailable",
            )
        return CompatibilityDecision(
            artifact_class,
            generation,
            rule.action,
            rule.target_generation,
            rule.runtime_profile,
            rule.migration_steps,
        )

    def simulate_creation_v2_transition(self) -> "CompatibilityProgramme":
        """Model the retention rule required before a future creation/2 release.

        This is a programme falsification fixture, not a claim that creation/2
        exists. It demonstrates that introducing a successor moves creation/1 to
        exact retained-runtime execution rather than silently reinterpreting it.
        """
        rules = []
        for rule in self._rules.values():
            if rule.artifact_class is ArtifactClass.CREATION and rule.generation == "splashmx.creation/1":
                rules.append(replace(rule, action=CompatibilityAction.RETAINED_RUNTIME))
            else:
                rules.append(rule)
        rules.append(
            GenerationRule(
                ArtifactClass.CREATION,
                "splashmx.creation/2",
                CompatibilityAction.DIRECT,
                runtime_profile="splashmx.generic-player/2",
            )
        )
        return CompatibilityProgramme(rules, max_migration_steps=self.max_migration_steps)


def estimate_retained_runtime_bytes(runtimes: Iterable[RetainedRuntime]) -> int:
    """Conservative storage model: immutable digest is deduped per deployment copy.

    Multiple references to the same profile+digest do not multiply storage. If
    the same bytes are deliberately deployed to N independent copies/regions,
    N is explicit rather than hidden in the estimate.
    """
    by_identity: dict[tuple[str, str], RetainedRuntime] = {}
    for runtime in runtimes:
        key = (runtime.profile, runtime.digest)
        prior = by_identity.get(key)
        if prior is None or runtime.deployment_copies > prior.deployment_copies:
            by_identity[key] = runtime
    return sum(row.size_bytes * row.deployment_copies for row in by_identity.values())
