from enum import IntEnum


class SubsonicError(IntEnum):
    GENERIC = 0
    REQUIRED_PARAM_MISSING = 10
    CLIENT_MUST_UPGRADE = 20
    SERVER_MUST_UPGRADE = 30
    WRONG_USERNAME_OR_PASSWORD = 40
    TOKEN_AUTH_NOT_SUPPORTED = 41
    NOT_AUTHORIZED = 50
    TRIAL_OVER = 60
    NOT_FOUND = 70


ERROR_MESSAGES = {
    SubsonicError.GENERIC: "A generic error.",
    SubsonicError.REQUIRED_PARAM_MISSING: "Required parameter is missing.",
    SubsonicError.CLIENT_MUST_UPGRADE: "Incompatible Subsonic REST protocol version. Client must upgrade.",
    SubsonicError.SERVER_MUST_UPGRADE: "Incompatible Subsonic REST protocol version. Server must upgrade.",
    SubsonicError.WRONG_USERNAME_OR_PASSWORD: "Wrong username or password.",
    SubsonicError.TOKEN_AUTH_NOT_SUPPORTED: "Token authentication not supported.",
    SubsonicError.NOT_AUTHORIZED: "User is not authorized for the given operation.",
    SubsonicError.TRIAL_OVER: "The trial period is over.",
    SubsonicError.NOT_FOUND: "The requested data was not found.",
}
