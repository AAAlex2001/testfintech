from fastapi import APIRouter

from api.deps import gate_nambaone
from gate_lib.api.v2 import build_ping_method
from gate_lib.api.v2 import build_refund_method
from gate_lib.api.v2 import build_refund_status_method
from gate_lib.api.v2 import build_sale_without_card_method
from gate_lib.api.v2 import build_status_method
from gate_lib.api.v2 import build_terminal_data_schema_method

router = APIRouter(tags=["v2"])

build_ping_method(router)
build_terminal_data_schema_method(router, gate_nambaone)
build_sale_without_card_method(router, gate_nambaone)
build_status_method(router, gate_nambaone)
build_refund_method(router, gate_nambaone)
build_refund_status_method(router, gate_nambaone)
