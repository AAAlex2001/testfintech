from fastapi import Request
from gate_{{cookiecutter.gate_name}}.gate_{{cookiecutter.gate_name}} import Gate{{cookiecutter.gate_name_camel}}
from gate_{{cookiecutter.gate_name}}.gate_{{cookiecutter.gate_name}} import get_gate_{{cookiecutter.gate_name}}


def gate_{{cookiecutter.gate_name}}(request: Request) -> Gate{{cookiecutter.gate_name_camel}}:
    return get_gate_{{cookiecutter.gate_name}}(
        httpx_client=request.app.state.httpx_client,
        aiojobs_scheduler=request.app.state.aiojobs_scheduler,
    )
