# Hybrid Agentic Workflow Specification

This document describes the **Hybrid Agentic Workflow** specification, which extends the [Serverless Workflow DSL](https://serverlessworkflow.io) to support autonomous AI Agents.

## Concept

Traditional workflows are **deterministic**: `Input -> Step A -> Step B -> Output`.
Agentic Workflows are **probabilistic**: `Goal -> Agent (Think/Act loop) -> Result`.

This specification supports a **Hybrid** approach where:
1.  **Orchestration**: The deterministic workflow acts as the "Manager", handling state, approvals, and routing.
2.  **Autonomy**: Specific steps are delegated to "Agents" to solve complex, non-deterministic problems.

## Key Changes

### 1. `use.agents` Definition

You can now define reusable agents in the `use` block, similar to how you define `functions`.

```yaml
use:
  functions:
    googleSearch:
      type: custom
      operation: search_tool
      
  agents:
    researcher:
      title: "Senior Research Assistant"
      model: "gpt-4-turbo"
      systemPrompt: "You are an expert researcher. Use tools to find facts."
      capabilities:
         - googleSearch
      dataStores:
         - myKnowledgeBase
      reasoning:
         scheme: react
      examples:
         - query: "Find me flights to Paris"
           thought: "I need to check flight availability."
           action: "googleSearch(paris flights)"
  
  dataStores:
      myKnowledgeBase:
          type: vector
          uri: "gs://my-bucket/vector-index"
```

### 2. `agent` Task Type

A new state type `agent` (or `agentTask` in the schema) delegates control to an LLM loop.

```yaml
do:
  - name: MarketResearch
    type: agent
    agent: researcher # Reference to the agent above
    goal: "Find the top 3 competitors for ${ .input.productName }"
    constraints:
      maxIterations: 10
      timeout: "PT5M"
    # The output of this task is the final answer from the Agent
```

### 3. Inline Agents

You can also define agents inline if they are one-off.

```yaml
do:
  - name: Summarize
    type: agent
    agent:
      model: "claude-3-opus"
      systemPrompt: "Summarize this text concisely."
    goal: "Summarize the following: ${ .marketResearchResult }"
```

## Schema Details

The schema extension includes:
- **`Agent`**: Properties for `model`, `systemPrompt`, `temperature`, `capabilities` (tools), `dataStores` (RAG), `reasoning` (cognitive architecture), and `examples`.
- **`AgentTask`**: Properties for `agent` (ref or inline), `goal` (prompt), `context` (history/files), and `constraints`.

## Cognitive Architecture Support

Based on the [Agents Whitepaper](./22365_19_Agents_v8.pdf), this specification supports:

1.  **Tools**: Defined via `use.functions` (Extensions) and `use.agents` capabilities.
2.  **Data Stores (RAG)**: Explicit support for `use.dataStores` to ground agents in factual data.
3.  **Reasoning**: Configurable `reasoning.scheme` (ReAct, CoT, etc.) and `examples` for few-shot prompting to guide the agent's orchestration layer.

## Dynamic Subflows

Support for **Agent-Generated Workflows**. An agent can generate a full workflow definition, which the orchestrator then executes immediately.

### Pattern: Plan & Execute

1.  **Agent Task**: Generates a workflow definition (YAML/JSON) based on a high-level goal.
2.  **Run Task**: Executes the generated definition.

```yaml
do:
  - name: CreatePlan
    type: agent
    agent: planner_agent
    goal: "Create a workflow to process order ${ .input.orderId }"
    output:
       as: "${ .plan }" # Save the generated workflow YAML/JSON to variable 'plan'

  - name: ExecutePlan
    type: run
    run:
      workflow:
        definition: "${ .plan }" # Inject the generated definition
```

This allows for **Runtime Orchestration**, where the steps are not known at deploy time but decided by the AI.
