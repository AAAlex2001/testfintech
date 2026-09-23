from pydantic import BaseModel


class InvoiceNotification(BaseModel):
    Param: str | dict | float | bool | None
    Amount: str | int | float | None = None


class WithdrawalNotification(BaseModel):
    Param: str | dict | float | bool | None
    Amount: str | int | float | None = None
