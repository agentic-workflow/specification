# Agentic Workflow Specification

Agentic Workflow 1.0.3 is a compatible extension of Open Workflow 1.0.3 for
AI-assisted and human-in-the-loop orchestration. The version remains `1.0.3`
to make the upstream synchronization point explicit.

The exact upstream source is pinned in
[`schema/open-workflow-1.0.3.provenance.yaml`](schema/open-workflow-1.0.3.provenance.yaml).

## Compatibility policy

- Open Workflow 1.0.3 is the normative orchestration core.
- Agentic additions are additive: agent, ask, assert, rule, JSON-RPC/OpenRPC,
  reusable MCP sessions, data stores, and explanatory/idempotency metadata.
- Canonical Open Workflow MCP syntax and the existing Agentic MCP shorthand are
  both accepted. New portable workflows should prefer the canonical syntax.
- The supported expression language is declared with top-level `evaluate`.
  The current Light Workflow runtime executes CEL definitions and therefore
  requires an explicit `evaluate.language: cel`. Open Workflow defaults an
  omitted evaluation configuration to `jq`, which Light Workflow rejects at
  admission rather than passing jq expressions to its CEL evaluator.
- Schema acceptance and runtime execution are separate capabilities. The
  runtime rejects an unimplemented task, call, language, or transport before a
  process is persisted.

## Agent call

The executable agent form is `call: agent`:

```yaml
document:
  dsl: 1.0.3
  namespace: examples
  name: review-customer
  version: 1.0.0
evaluate:
  language: cel
do:
  - review:
      call: agent
      with:
        agent: customer-reviewer
        mode: service
        input: '${{ customer }}'
        outputSchema:
          type: object
          required: [decision]
```

The older standalone `agentTask` schema remains readable for 1.0 compatibility
but is deprecated because the Rust runtime uses `call: agent`.

## Legacy compatibility

Open Workflow 1.0.3 uses argv arrays for `run.script.arguments` and
`run.shell.arguments`, and requires `authority` plus `grant` in inline OAuth2
and OIDC authentication properties. Agentic Workflow 1.0.3 also accepts the
older argument maps and incomplete inline authentication objects so existing
Agentic documents remain schema-readable. The argument-map branches and
incomplete authentication shapes are compatibility-only; new documents should
use the canonical Open Workflow forms.

### Runtime migration for expression evaluation

Open Workflow treats an omitted `evaluate` configuration as jq, while Light
Workflow executes CEL only. Existing stored definitions without `evaluate`
remain schema-readable, but attempts to create new processes from them will
fail admission after the runtime upgrade. Add the following before upgrading:

```yaml
evaluate:
  language: cel
```

The admission check does not rewrite or revalidate existing in-flight process
snapshots.

## Canonical MCP call

```yaml
do:
  - lookup-customer:
      call: mcp
      with:
        protocolVersion: '2025-06-18'
        method: tools/call
        parameters:
          name: customer_lookup
          arguments:
            customerId: '${{ customerId }}'
        transport:
          http:
            endpoint: https://gateway.example/mcp
```

The Agentic shorthand remains available when a durable workflow needs a named,
reusable session:

```yaml
use:
  mcpSessions:
    gateway:
      server:
        endpoint: https://gateway.example/mcp
        transport: streamable-http
do:
  - lookup-customer:
      call: mcp
      with:
        session: gateway
        tool: customer_lookup
        arguments:
          customerId: '${{ customerId }}'
```

## Conformance check

The local check validates the Draft 2020-12 schema, representative upstream and
Agentic fixtures, ambiguous MCP rejection, and the pinned upstream surface:

```bash
./scripts/check-schema-conformance.py --upstream /path/to/open-workflow-1.0.3-workflow.yaml
```

The supplied upstream file must match the checksum recorded in the provenance
file. Running without `--upstream` still performs local schema and fixture
validation. The GitHub Actions conformance job always downloads the pinned
source and runs the strict upstream comparison.
