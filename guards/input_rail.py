from agents import input_guardrail, GuardrailFunctionOutput, RunContextWrapper, Agent
from pydantic import BaseModel
import os


class PathCheck(BaseModel):
    is_valid: bool
    reasoning: str


@input_guardrail
async def validate_repo_path(ctx: RunContextWrapper, agent: Agent, input_data: str) -> GuardrailFunctionOutput:
    # simple deterministic check — no LLM needed for this one
    is_valid = True
    reasoning = "OK"

    # crude path extraction check; adjust to your needs
    if "/" in input_data:
        possible_path = [w for w in input_data.split() if w.startswith("/")]
        if possible_path and not os.path.isdir(possible_path[0]):
            is_valid = False
            reasoning = f"Path {possible_path[0]} does not exist"

    return GuardrailFunctionOutput(
        output_info=reasoning,
        tripwire_triggered=not is_valid,
    )