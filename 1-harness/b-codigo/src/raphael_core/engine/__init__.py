"""Motor de brigadas: spec declarativo, jefe genérico, efímeros con tools y los contratos efímero -> jefe -> orquestador.

Portado de JarvisRemote (H4). Ver `chief.py` para el modelo de interacción y `reports.py` para los contratos."""

from .chief import Chief, ChiefSettings, Delegation, Plan
from .helper import Helper, NoModel, StepLimit, personalize
from .live import LiveBoard
from .reports import REPORT_VERSION, ContractInvalid, HelperResult, InternalReport
from .spec import BrigadeSpec, Criterion, HelperSpec, RouteRule, Routing, SkillSpec, StepSpec, ValidationSpec, WatchSpec

__all__ = [
    "REPORT_VERSION", "BrigadeSpec", "Chief", "ChiefSettings", "ContractInvalid", "Criterion", "Delegation", "Helper",
    "HelperResult", "HelperSpec", "InternalReport", "LiveBoard", "NoModel", "Plan", "RouteRule", "Routing", "SkillSpec",
    "StepLimit", "StepSpec", "ValidationSpec", "WatchSpec", "personalize",
]
