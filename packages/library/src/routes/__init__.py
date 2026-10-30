"""Flask 蓝图注册入口。

各蓝图均通过 url_prefix='/api' 前缀注册，路由路径不含 /api 前缀。
"""
from flask import Blueprint

# Lazy import to avoid circular references at module load time
_imported = False


def register_blueprints(app):
    global _imported
    if _imported:
        return

    from . import misc_routes
    from . import video_routes
    from . import dim_routes
    from . import data_routes
    from . import hmd_routes
    from . import upload_routes
    from . import template_routes

    app.register_blueprint(misc_routes.bp)
    app.register_blueprint(video_routes.bp)
    app.register_blueprint(dim_routes.bp)
    app.register_blueprint(data_routes.bp)
    app.register_blueprint(hmd_routes.bp)
    app.register_blueprint(upload_routes.bp)
    app.register_blueprint(template_routes.bp)

    _imported = True