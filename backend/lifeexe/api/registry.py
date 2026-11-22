from lifeexe.api.routing import Api

#: The single route registry for /api/v1. Route modules register on import.
api = Api(prefix="/api/v1")
