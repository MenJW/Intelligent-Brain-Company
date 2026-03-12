# Agent Contracts

## Goal

Each department agent returns structured JSON so the orchestration layer can validate outputs, regenerate specific stages, diff versions, and support direct chat without parsing brittle free-form prose.

## Department Solution Contract

Each department planning agent returns:

```json
{
  "solutions": [
    {
      "name": "string",
      "summary": "string",
      "feasibility_score": 1,
      "dependencies": ["hardware", "design"],
      "assumptions": ["string"],
      "rationale": "string",
      "implementation_steps": ["string"],
      "success_metrics": ["string"],
      "artifacts": {
        "department_specific_key": "value"
      }
    }
  ]
}
```

## Department Artifact Keys

- hardware: bom_targets, manufacturing_notes, certification_path, supply_chain_risks
- software: interface_boundaries, system_components, data_flows, operational_risks
- design: design_constraints, ergonomic_targets, safety_cues, serviceability_rules
- marketing: channel_budget, wedge_segments, launch_narrative, partnership_plan
- finance: capital_envelope, pricing_logic, unit_economics, downside_controls

## Research Contract

```json
{
  "customer_segments": ["string"],
  "market_size_view": "string",
  "competitive_landscape": "string",
  "key_risks": ["string"],
  "recommendation": "string"
}
```

## Board Contract

```json
{
  "approved": true,
  "development_difficulty": "string",
  "budget_outlook": "string",
  "funding_cycle": "string",
  "rationale": "string",
  "conditions": ["string"]
}
```

## Chat Contract

```json
{
  "reply": "string",
  "follow_up_questions": ["string"],
  "updated_assumptions": ["string"],
  "suggested_stage": "string",
  "suggested_impact": "string",
  "can_promote_to_intervention": true
}
```