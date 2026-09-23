from pydantic import BaseModel


class TerminalData(BaseModel):
    provider_base_url: str
    proxy_url: str
    secure_redirect_url: str | None = None
