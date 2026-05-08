"""Pydantic schemas shared across the engine."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Letter = Literal["A", "B", "C", "D", "E"]
Tier = Literal["easy", "medium", "hard", "extreme", "self", "n/a"]
RunStatus = Literal["queued", "running", "paused", "completed", "failed", "killed"]


class ImageInput(BaseModel):
    path: str
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    role: str  # "base", "option_a", ... "option_d"
    # Public URL (e.g. Azure CDN). When present, providers that prefer URLs
    # (OpenRouter-on-Fal vision) use this directly; providers that need bytes
    # fall back to `path`.
    url: str | None = None


class Subject(BaseModel):
    person_id: str
    real_or_synthetic: Literal["real", "synthetic"]
    license: str
    source: str


class Option(BaseModel):
    model_config = ConfigDict(extra="allow")
    image: str | None = None
    kind: Literal["distractor", "true_match"] | None = None
    similarity_tier: Tier | None = None
    similarity_cosine: float | None = None
    source: str | None = None
    person_id: str | None = None
    generated_by: str | None = None
    fal_request_id: str | None = None
    is_none_of_the_above: bool | None = None
    cdn_url: str | None = None


class SampleMeta(BaseModel):
    """One MCQ item (the on-disk meta.json)."""
    model_config = ConfigDict(extra="allow")
    id: str
    schema_version: str = "1.0.0"
    task_type: str = "mcq_likeness"
    subject: Subject | None = None
    base_image: str
    base_cdn_url: str | None = None
    options: dict[Letter, Option]
    correct_answer: Letter
    none_of_the_above_is_correct: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_options(self) -> "SampleMeta":
        if "E" not in self.options:
            self.options["E"] = Option(is_none_of_the_above=True)
        e = self.options["E"]
        if not e.is_none_of_the_above:
            raise ValueError("Option E must have is_none_of_the_above=true")
        if self.correct_answer == "E":
            if not self.none_of_the_above_is_correct:
                raise ValueError("correct_answer=E requires none_of_the_above_is_correct=true")
            for letter in ("A", "B", "C", "D"):
                opt = self.options.get(letter)
                if opt and opt.kind == "true_match":
                    raise ValueError("Type B sample must have no true_match")
        else:
            if self.none_of_the_above_is_correct:
                raise ValueError("none_of_the_above_is_correct=true requires correct_answer=E")
            opt = self.options.get(self.correct_answer)
            if not opt or opt.kind != "true_match":
                raise ValueError(f"correct_answer={self.correct_answer} must be true_match")
        return self


class Sample(BaseModel):
    """A loaded sample with resolved absolute image paths."""
    meta: SampleMeta
    sample_dir: Path

    def image_path(self, letter: Letter | Literal["base"]) -> Path:
        if letter == "base":
            return self.sample_dir / self.meta.base_image
        opt = self.meta.options[letter]
        if not opt.image:
            raise ValueError(f"Option {letter} has no image")
        return self.sample_dir / opt.image


class BenchmarkManifest(BaseModel):
    benchmark_id: str
    title: str
    description: str = ""
    task_type: str = "mcq_likeness"
    sample_ids: list[str]
    benchmark_hash: str = ""
    schema_version: str = "1.0.0"


class ProviderResponse(BaseModel):
    raw_text: str
    parsed_choice: Letter | None = None
    refusal: bool = False
    refusal_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider_request_id: str | None = None
    finish_reason: str | None = None
    error: str | None = None


class SampleResult(BaseModel):
    sample_id: str
    tier: str | None = None
    presence: Literal["correct_present", "correct_absent"] | None = None
    answer: Letter
    predicted: Letter | None
    correct: bool
    raw_output: str
    refusal: bool = False
    parse_failure: bool = False
    latency_ms: int = 0
    cost_usd: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    completed_at: str = ""


class RunSummary(BaseModel):
    overall_accuracy: float
    overall_ci95: tuple[float, float]
    accuracy_by_tier: dict[str, float] = Field(default_factory=dict)
    accuracy_when_present: float = 0.0
    accuracy_when_absent: float = 0.0
    none_selection_rate: dict[str, float] = Field(default_factory=dict)
    refusal_rate: float = 0.0
    parse_failure_rate: float = 0.0
    composite_likeness_score: float = 0.0
    confusion_matrix: list[list[int]] = Field(default_factory=list)


class RunResult(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    benchmark_id: str
    model_id: str
    model_display: str
    model_family: str
    benchmark_hash: str = ""
    n_samples: int
    started_at: str
    completed_at: str | None = None
    metrics: RunSummary | None = None
    cost: dict[str, float] = Field(default_factory=dict)
    latency: dict[str, float] = Field(default_factory=dict)


class RunControlState(BaseModel):
    """On-disk state used to coordinate live run control across processes."""
    run_id: str
    status: RunStatus
    requested_action: Literal["none", "pause", "resume", "kill"] = "none"
    n_samples: int
    completed: int = 0
    started_at: str
    updated_at: str
    model_id: str
    benchmark_id: str
    last_error: str | None = None
    pid: int | None = None
