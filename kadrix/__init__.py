# Kadrix — Sistema de Gestión de Proyectos y Mantenimiento de Fixtures
# Cliente: Cadrex / Adriana Ramos
from flask import Blueprint

kadrix_bp = Blueprint("cadrex", __name__, url_prefix="/cadrex")

from . import views  # noqa: E402, F401
from . import analytics  # noqa: E402, F401
