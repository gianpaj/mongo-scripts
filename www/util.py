from functools import wraps


def memoize(func):
    remembered = {}
    @wraps(func)
    def inner(*args):
        try:
            return remembered[args]
        except KeyError:
            remembered[args] = func(*args)
            return remembered[args]
    return inner

@memoize
def _url_split(url):
    """
    Return a list of URL segments, with None in
    place of wildcard path segments. Wildcards
    are:

    (.*)
    .*
    (.+)
    .+
    [^/]+
    [^/]*
    ([^/]+)
    ([^/]*)

    >>> _url_split('/foo/bar')
    ['', 'foo', 'bar']
    >>> _url_split('foo/bar')
    ['foo', 'bar']
    >>> _url_split('/foo/.*')
    ['', 'foo', None]
    >>> _url_split('/foo/.*/(.*)/baz')
    ['', 'foo', None, None, 'baz']
    >>> _url_split('/foo/.*/([^/]+)/baz')
    ['', 'foo', None, None, 'baz']
    >>> _url_split('[^/]*')
    [None]
    >>> _url_split('/foo/[^/]*')
    ['', 'foo', None]
    """
    wildcards = ('(.*)', '.*', '(.+)', '.+', '[^/]+', '[^/]*', '([^/]+)', '([^/]*)')
    parts = url.split('/')

    # since some wildcards contain "/", we might have to
    # reassemble some of the parts into larger wholes
    newparts = [parts[0]]
    for i in range(1, len(parts)):
        a, b = parts[i-1], parts[i]
        combined = '%s/%s' % (a, b)
        if combined in wildcards:
            newparts[-1] = combined
        else:
            newparts.append(b)

    parts = newparts
    for i in xrange(len(parts)):
        parts[i] = parts[i] if parts[i] not in wildcards else None
    return parts

@memoize
def url_cmp(a, b):
    """
    comparator for list.sort() that orders URLs
    by specificity, with the most specific URLs
    first. URLs that are equally specific are
    considered equal (this ensures that they remain
    in the same relative order they were originally,
    since list.sort() is stable).

    Specificity is defined like so:

        * A longer URL with is more specific than
          a shorter URL
        * A URL with a wildcard ("(.*)" or ".*", eg)
          is considered less specific than a URL with
          a specific value in that path component
          position

    >>> url_cmp('/foo', '/bar')
    0
    >>> url_cmp('/foo/bar', '/baz')
    -1
    >>> url_cmp('/foo/(.*)', '/foo/bar')
    1
    >>> url_cmp('/foo/bar', '/foo/(.*)')
    -1
    >>> url_cmp('/foo/(.*)', '/foo/.*')
    0
    >>> l = ['/(.*)', '/foo/bar', '/foo/(.*)', '/baz']
    >>> l.sort(cmp=url_cmp)
    >>> l
    ['/foo/bar', '/foo/(.*)', '/baz', '/(.*)']
    """
    aparts = _url_split(a)
    bparts = _url_split(b)

    if len(aparts) > len(bparts):
        return -1
    elif len(bparts) > len(aparts):
        return 1

    for apart, bpart in zip(aparts, bparts):
        if apart is None and bpart is None:
            continue
        elif apart is None:
            return 1
        elif bpart is None:
            return -1

    return 0

