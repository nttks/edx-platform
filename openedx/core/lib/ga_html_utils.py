"""
Utility for html template
"""

CIRCLE_NUMBER_REF = [
    '&#9312;', '&#9313;', '&#9314;', '&#9315;', '&#9316;'
]


def get_circle_number(number):
    if number < 1 or number > len(CIRCLE_NUMBER_REF):
        raise AttributeError('{} is not support. Support only between 1 to {}'.format(number, len(CIRCLE_NUMBER_REF)))
    return CIRCLE_NUMBER_REF[number - 1]
