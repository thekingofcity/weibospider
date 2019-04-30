class CookieGenException(Exception):
    """
    Failed to gen sub and subp cookies without login
    """


class Timeout(Exception):
    """
    Function run timeout
    """


class LoginException(Exception):
    """
    Login error for weibo login
    """

class LoginWrongPasswordException(LoginException):
    def __init__(self, name):
        self.name = name


class LoginAccountForbiddenException(LoginException):
    def __init__(self, name):
        self.name = name


class LoginDecodeException(LoginException):
    def __init__(self, name):
        self.name = name
