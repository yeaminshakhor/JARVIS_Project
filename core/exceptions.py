class JarvisError(Exception):
    pass


class AuthError(JarvisError):
    pass


class APIError(JarvisError):
    pass


class ResourceError(JarvisError):
    pass


class ConfigError(JarvisError):
    pass
