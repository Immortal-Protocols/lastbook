/// The library's own routes, one group per area (desktop: sections of server.py and engine/library.py).
enum Routes {
    static var all: [RouteGroup] { [VideosAPI(), LibraryAPI(), MapAPI(), ChatAPI(), ReadinessAPI()] }
}
