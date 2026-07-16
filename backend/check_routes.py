from app.main import app
import sys

def get_routes(router, prefix=""):
    resolved_routes = []
    # In FastAPI, app.routes contains APIRoute, Route, or _IncludedRouter objects
    for route in router.routes:
        route_type = type(route).__name__
        if route_type == "_IncludedRouter":
            # IncludedRouter contains a context with the router and the prefix
            ctx = getattr(route, "include_context", None)
            if ctx:
                sub_router = ctx.included_router
                sub_prefix = prefix + ctx.prefix
                resolved_routes.extend(get_routes(sub_router, sub_prefix))
        elif hasattr(route, "routes"):
            # Mount or other router containers
            sub_prefix = prefix + getattr(route, "path", "")
            resolved_routes.extend(get_routes(route, sub_prefix))
        else:
            # APIRoute or Route
            path = prefix + getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            name = getattr(route, "name", "")
            tags = getattr(route, "tags", [])
            resolved_routes.append((methods, path, name, tags))
    return resolved_routes

def list_all_routes():
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    all_resolved = get_routes(app)
    print(f"Total resolved routes: {len(all_resolved)}")
    
    # Group by tags/prefix
    routes_by_group = {}
    for methods, path, name, tags in all_resolved:
        # Skip openapi or swagger docs urls
        if path in ["/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"]:
            continue
            
        group = tags[0] if tags else "General"
        if group not in routes_by_group:
            routes_by_group[group] = []
        routes_by_group[group].append((methods, path, name))
        
    for group, routes in sorted(routes_by_group.items()):
        print(f"\n📂 Group: {group}")
        print("=" * 70)
        for methods, path, name in sorted(routes, key=lambda x: x[1]):
            method_str = ", ".join(sorted(list(methods)))
            print(f"[{method_str}] {path} -> {name}")

if __name__ == "__main__":
    list_all_routes()
