from __future__ import annotations

import yaml

from sindri.models import Component, ComponentType, DesignGraph

IMAGE_TYPE_MAP: dict[str, ComponentType] = {
    "postgres": ComponentType.RELATIONAL_DB,
    "mysql": ComponentType.RELATIONAL_DB,
    "mariadb": ComponentType.RELATIONAL_DB,
    "redis": ComponentType.CACHE,
    "memcached": ComponentType.CACHE,
    "kafka": ComponentType.QUEUE,
    "rabbitmq": ComponentType.QUEUE,
    "nginx": ComponentType.LOAD_BALANCER,
    "haproxy": ComponentType.LOAD_BALANCER,
    "traefik": ComponentType.LOAD_BALANCER,
    "minio": ComponentType.OBJECT_STORE,
}


def classify_image(image: str) -> ComponentType:
    name = image.lower()
    for key, ctype in IMAGE_TYPE_MAP.items():
        if key in name:
            return ctype
    return ComponentType.UNKNOWN


def parse_compose(yaml_text: str) -> DesignGraph:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return DesignGraph(components=[])
    if not isinstance(data, dict):
        return DesignGraph(components=[])
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return DesignGraph(components=[])

    components: list[Component] = []
    for name, spec in services.items():
        spec = spec or {}
        image = spec.get("image") if isinstance(spec, dict) else None
        if image:
            ctype = classify_image(str(image))
        elif isinstance(spec, dict) and "build" in spec:
            ctype = ComponentType.APP_SERVER
        else:
            ctype = ComponentType.UNKNOWN
        components.append(Component(name=str(name), type=ctype))
    return DesignGraph(components=components)
