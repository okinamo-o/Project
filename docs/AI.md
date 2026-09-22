# NEXUS Generative AI Reasoning & Decision Support

## 1. Architectural Role of Gemini

In NEXUS, Gemini functions exclusively as the **High-Level Advisory & Reasoning Layer**, adhering to the core project rule:
> **Gemini is the reasoning layer, not the entire system.**

```
Physical / IoT Sensors + Computer Vision + Acoustic Intelligence
                                ↓
                 Local Signal Processing & ML Models
                                ↓
                Structured Telemetry & Event Matrix
                                ↓
              Explicit Multimodal Fusion Hypothesis
                                ↓
        Gemini Reasoning Engine (Selective, Grounded Context)
                                ↓
        Forensic Explanations, Root Cause, Actionable CAPA
                                ↓
                 NEXUS Operations Command Center
```

---

## 2. Core Capabilities

1. **Incident Explanation**: Explains why NEXUS triggered an alarm by breaking down the independent physical signals, their temporal sequence, and cross-modal correlation.
2. **Operator Assistant ("Ask NEXUS...")**: Natural-language Q&A enabling facility managers to query room states, historical comparisons, and device status without writing SQL.
3. **Automated Safety Briefings & Reports**: Compiles verified post-incident technical briefings with executive summary, timeline, and corrective/preventive actions (CAPA).
4. **"What If?" Sensitivity Analysis**: Explains changes in system confidence when sensors are disabled or altered.

---

## 3. Dedicated Prompt Directory (`ai/prompts/`)

* `incident_explanation.txt`: Synthesizes evidence matrix and timeline into a risk diagnostic.
* `operator_assistant.txt`: Bounds the assistant strictly to the live building telemetry context.
* `report_generation.txt`: Formats a formal engineering briefing for facility leadership.
* `evidence_analysis.txt`: Evaluates multi-signal correlation and individual signal contribution.

---

## 4. Local Offline / Degraded Mode Guarantee

NEXUS does not have an external cloud single point of failure:
* When `GEMINI_API_KEY` is provided, NEXUS connects to Gemini (`gemini-2.5-flash`).
* When no key is provided or network connectivity is severed, NEXUS automatically falls back to its deterministic local expert reasoning engine.
* The UI clearly highlights `AI ONLINE` or `AI LOCAL DEGRADED MODE`.
