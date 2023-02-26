from silicon.routes import healthcheck, sds

__all__ = ["routers"]

routers = [
    healthcheck.router,
    sds.router,
]
