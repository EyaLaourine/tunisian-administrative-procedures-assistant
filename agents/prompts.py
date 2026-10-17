"""Versioned prompt library loader (prompts/registry.yaml + prompts/<name>/<version>.yaml)."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PromptSpec(BaseModel):
    name: str
    version: str
    description: str = ""
    model_role: str = Field(default="llm", pattern="^(llm|translation)$")
    options: dict = Field(default_factory=dict)
    json_output: bool = False
    response_schema: dict | None = None
    system: str = ""
    user_template: str

    def render(self, **values: str) -> tuple[str, str]:
        """Returns (system, user). Only `{key}` placeholders for the given keys are substituted,
        so literal braces (e.g. JSON examples) in the prompt text are left untouched."""

        def fill(template: str) -> str:
            for key, value in values.items():
                template = template.replace("{" + key + "}", value)
            return template

        return fill(self.system), fill(self.user_template)

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


class PromptLibrary:
    def __init__(self, root: Path):
        self.root = root
        registry = yaml.safe_load((root / "registry.yaml").read_text(encoding="utf-8")) or {}
        self.active: dict[str, str] = registry.get("active", {})

    def get(self, name: str, version: str | None = None) -> PromptSpec:
        version = version or self.active.get(name)
        if not version:
            raise KeyError(f"no active version for prompt {name!r}")
        path = self.root / name / f"{version}.yaml"
        spec = PromptSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if spec.name != name or spec.version != version:
            raise ValueError(f"{path} declares {spec.ref}, expected {name}@{version}")
        return spec

    def list_versions(self) -> dict[str, dict]:
        out = {}
        for d in sorted(p for p in self.root.iterdir() if p.is_dir()):
            out[d.name] = {"active": self.active.get(d.name), "versions": sorted(f.stem for f in d.glob("*.yaml"))}
        return out


@lru_cache
def get_library(root: Path) -> PromptLibrary:
    return PromptLibrary(root)
