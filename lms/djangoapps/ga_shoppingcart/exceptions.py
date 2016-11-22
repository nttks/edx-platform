"""
Exceptions for the ga_shoppingcart app.
"""


class CourseException(Exception):
    pass


class InvalidOrder(CourseException):
    pass
