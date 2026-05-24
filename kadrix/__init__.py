# Kadrix — Sistema de Gestión de Proyectos y Mantenimiento de Fixtures
# Cliente: Cadrex / Adriana Ramos
from flask import Blueprint

kadrix_bp = Blueprint("kadrix", __name__, url_prefix="/kadrix")

from . import views  # noqa: E402, F401
