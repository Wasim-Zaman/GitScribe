from agents import output_guardrail, GuardrailFunctionOutput, RunContextWrapper, Agent
from pydantic import BaseModel
import os

class ReportCheck(BaseModel):
    is_valid: bool
    reasoning: str


@output_guardrail
async def validate_report_output(ctx, agent, output: str) -> GuardrailFunctionOutput:
    is_valid = output.strip() == "" or "Title" in output or "|" in output or len(output.splitlines()) > 3
    reasoning = "OK" if is_valid else "Output looks like a summary, not the full report"
    return GuardrailFunctionOutput(output_info=reasoning, tripwire_triggered=not is_valid)