import threading


def between(L, R, id_):
    return (L < R and (L < id_ < R)) or (L > R and (L < id_ or id_ < R))


def async_void_call(target, daemon=True, *args, **kwargs):
    th = threading.Thread(name=f"async-{target.__name__}:{threading.time.time_ns()}",
                          target=lambda: target(args, kwargs), daemon=daemon)
    th.start()
    return th
