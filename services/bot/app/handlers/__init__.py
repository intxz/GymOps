from app.handlers.dynamic_exercise import router as dynamic_exercise_router
from app.handlers.fallback import router as fallback_router
from app.handlers.reserved import router as reserved_router

__all__ = ["reserved_router", "dynamic_exercise_router", "fallback_router"]
