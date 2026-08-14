#!/usr/bin/env python3
"""Check the Agentic 1.0.3 schema and its pinned Open Workflow baseline."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
AGENTIC_SCHEMA = ROOT / "schema" / "workflow.yaml"
PROVENANCE = ROOT / "schema" / "open-workflow-1.0.3.provenance.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a YAML object")
    return value


def call_variant(schema: dict[str, Any], title: str) -> dict[str, Any]:
    for variant in schema["$defs"]["callTask"]["oneOf"]:
        if variant.get("title") == title:
            return variant
    raise AssertionError(f"missing call variant {title}")


def with_schema(variant: dict[str, Any]) -> dict[str, Any]:
    return variant["allOf"][1]["properties"]["with"]


def run_process(schema: dict[str, Any], title: str) -> dict[str, Any]:
    for variant in schema["$defs"]["runTask"]["allOf"][1]["properties"]["run"][
        "oneOf"
    ]:
        if variant.get("title") == title:
            return variant
    raise AssertionError(f"missing run process variant {title}")


def assert_mapping_superset(upstream: Any, agentic: Any, path: str) -> None:
    if isinstance(upstream, dict):
        if not isinstance(agentic, dict):
            raise AssertionError(f"{path} changed type")
        for key, value in upstream.items():
            if key not in agentic:
                raise AssertionError(f"{path}.{key} is missing")
            assert_mapping_superset(value, agentic[key], f"{path}.{key}")
        return
    if isinstance(upstream, list):
        if not isinstance(agentic, list) or len(upstream) != len(agentic):
            raise AssertionError(f"{path} list shape drifted")
        for index, value in enumerate(upstream):
            assert_mapping_superset(value, agentic[index], f"{path}[{index}]")
        return
    if upstream != agentic:
        raise AssertionError(f"{path} drifted from Open Workflow 1.0.3")


def assert_agentic_invariants(agentic: dict[str, Any]) -> None:
    call_agent = with_schema(call_variant(agentic, "CallAgent"))
    call_reference_title = call_agent["properties"]["agent"]["title"]
    legacy_reference_title = agentic["$defs"]["agentTask"]["properties"]["agent"][
        "title"
    ]
    if call_reference_title == legacy_reference_title:
        raise AssertionError("call agent and legacy agentTask references need unique titles")


def assert_upstream_surface(agentic: dict[str, Any], upstream: dict[str, Any]) -> None:
    if agentic["properties"]["evaluate"] != upstream["properties"]["evaluate"]:
        raise AssertionError("top-level evaluate drifted from Open Workflow 1.0.3")
    for key in ("read",):
        if agentic["properties"]["schedule"]["properties"][key] != upstream["properties"][
            "schedule"
        ]["properties"][key]:
            raise AssertionError(f"schedule.{key} drifted from Open Workflow 1.0.3")

    upstream_tasks = {item["$ref"] for item in upstream["$defs"]["task"]["oneOf"]}
    agentic_tasks = {item["$ref"] for item in agentic["$defs"]["task"]["oneOf"]}
    missing_tasks = sorted(upstream_tasks - agentic_tasks)
    if missing_tasks:
        raise AssertionError(f"missing Open Workflow task variants: {missing_tasks}")

    upstream_calls = {
        variant["title"] for variant in upstream["$defs"]["callTask"]["oneOf"]
    }
    agentic_calls = {
        variant["title"] for variant in agentic["$defs"]["callTask"]["oneOf"]
    }
    missing_calls = sorted(upstream_calls - agentic_calls)
    if missing_calls:
        raise AssertionError(f"missing Open Workflow call variants: {missing_calls}")

    upstream_mcp = with_schema(call_variant(upstream, "CallMCP"))
    agentic_mcp = with_schema(call_variant(agentic, "CallMCP"))
    if agentic_mcp != upstream_mcp:
        raise AssertionError("canonical MCP call drifted from Open Workflow 1.0.3")
    call_variant(agentic, "CallLegacyMCP")

    for definition_name in (
        "emitTask",
        "errorFilter",
        "eventProperties",
        "forTask",
        "taskBase",
        "tryTask",
    ):
        assert_mapping_superset(
            upstream["$defs"][definition_name],
            agentic["$defs"][definition_name],
            f"$defs.{definition_name}",
        )

    upstream_oauth = upstream["$defs"]["oauth2AuthenticationProperties"]
    agentic_oauth = agentic["$defs"]["oauth2AuthenticationProperties"]
    if agentic_oauth["properties"] != upstream_oauth["properties"]:
        raise AssertionError("OAuth2 properties drifted from Open Workflow 1.0.3")
    if upstream_oauth.get("required") != ["authority", "grant"]:
        raise AssertionError("upstream OAuth2 requirements drifted")
    if "required" in agentic_oauth or "anyOf" in agentic_oauth or "oneOf" in agentic_oauth:
        raise AssertionError(
            "Agentic OAuth2 compatibility must remain unconstrained without generator variants"
        )
    if not agentic_oauth.get("$comment"):
        raise AssertionError("Agentic OAuth2 compatibility intent must be documented")

    for process_title, property_name in (
        ("RunScript", "script"),
        ("RunShell", "shell"),
    ):
        upstream_arguments = run_process(upstream, process_title)["properties"][
            property_name
        ]["properties"]["arguments"]
        agentic_arguments = run_process(agentic, process_title)["properties"][
            property_name
        ]["properties"]["arguments"]
        canonical_arguments = agentic_arguments.get("oneOf", [None])[0]
        for key in ("type", "items"):
            if canonical_arguments.get(key) != upstream_arguments.get(key):
                raise AssertionError(
                    f"{process_title} canonical arguments drifted from Open Workflow 1.0.3"
                )

    upstream_uri_options = upstream["$defs"]["uriTemplate"]["anyOf"]
    agentic_uri_options = agentic["$defs"]["uriTemplate"]["anyOf"]
    if agentic_uri_options[: len(upstream_uri_options)] != upstream_uri_options:
        raise AssertionError("canonical URI-reference options drifted from Open Workflow 1.0.3")


def validate_fixtures(schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    fixtures = ROOT / "tests" / "fixtures"
    valid_paths = sorted(fixtures.glob("valid-*.yaml"))
    invalid_paths = sorted(fixtures.glob("invalid-*.yaml"))
    if not valid_paths:
        raise AssertionError(f"no valid fixtures found in {fixtures}")
    if not invalid_paths:
        raise AssertionError(f"no invalid fixtures found in {fixtures}")
    for path in valid_paths:
        errors = sorted(
            validator.iter_errors(load_yaml(path)),
            key=lambda error: list(error.path),
        )
        if errors:
            details = "; ".join(error.message for error in errors[:5])
            raise AssertionError(f"{path.name} must be valid: {details}")
    for path in invalid_paths:
        if validator.is_valid(load_yaml(path)):
            raise AssertionError(f"{path.name} must be rejected")


def validate_upstream_fixtures(upstream: dict[str, Any]) -> None:
    validator = Draft202012Validator(upstream)
    paths = sorted((ROOT / "tests" / "fixtures").glob("valid-open-workflow-*.yaml"))
    if not paths:
        raise AssertionError("no canonical Open Workflow fixtures found")
    for path in paths:
        errors = sorted(
            validator.iter_errors(load_yaml(path)),
            key=lambda error: list(error.path),
        )
        if errors:
            details = "; ".join(error.message for error in errors[:5])
            raise AssertionError(
                f"{path.name} must be valid against Open Workflow 1.0.3: {details}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--upstream",
        type=Path,
        help="path to the pinned Open Workflow 1.0.3 schema",
    )
    args = parser.parse_args()

    agentic = load_yaml(AGENTIC_SCHEMA)
    provenance = load_yaml(PROVENANCE)
    if provenance.get("version") != "1.0.3":
        raise AssertionError("provenance version must remain 1.0.3")
    commit = provenance.get("commit")
    raw_schema = provenance.get("rawSchema")
    if not isinstance(commit, str) or len(commit) != 40:
        raise AssertionError("provenance commit must be a full Git commit id")
    if not isinstance(raw_schema, str) or commit not in raw_schema:
        raise AssertionError("provenance rawSchema must be pinned to provenance commit")
    expected_sha256 = provenance.get("sha256")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise AssertionError("provenance sha256 must be a 64-character digest")
    Draft202012Validator.check_schema(agentic)
    if agentic.get("$id") != "https://agentic-workflow.org/schemas/1.0.3/workflow.yaml":
        raise AssertionError("Agentic schema id must stay aligned at 1.0.3")
    assert_agentic_invariants(agentic)
    validate_fixtures(agentic)

    if args.upstream:
        digest = hashlib.sha256(args.upstream.read_bytes()).hexdigest()
        if digest != expected_sha256:
            raise AssertionError(
                f"upstream schema checksum mismatch: expected {expected_sha256}, got {digest}"
            )
        upstream = load_yaml(args.upstream)
        # PyYAML follows YAML 1.1 and resolves the unquoted key name `on` in the
        # upstream schedule properties and dependency list as boolean true.
        # Normalize that one known parser ambiguity to its YAML 1.2 meaning.
        schedule = upstream["properties"]["schedule"]
        schedule_properties = schedule["properties"]
        if True in schedule_properties:
            schedule_properties["on"] = schedule_properties.pop(True)
        dependencies = schedule.get("dependentRequired", {})
        if dependencies.get("read") == [True]:
            dependencies["read"] = ["on"]
        Draft202012Validator.check_schema(upstream)
        assert_upstream_surface(agentic, upstream)
        validate_upstream_fixtures(upstream)

    print("Agentic Workflow 1.0.3 schema conformance: PASS")


if __name__ == "__main__":
    main()
