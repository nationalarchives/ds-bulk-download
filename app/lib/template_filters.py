from urllib.parse import quote_plus

from tna_utilities.string import slugify as slugify_util


def slugify(s):
    return slugify_util(s)


def url_encode(s):
    return quote_plus(s)
