from app.handlers.admin import router as admin_router
from app.handlers.coaches import router as coaches_router
from app.handlers.dynamic_exercise import router as dynamic_exercise_router
from app.handlers.fallback import router as fallback_router
from app.handlers.mesocycles import router as mesocycles_router
from app.handlers.readiness import router as readiness_router
from app.handlers.reserved import router as reserved_router

__all__ = ["reserved_router", "dynamic_exercise_router", "fallback_router", "coaches_router", "mesocycles_router", "admin_router", "readiness_router"]
