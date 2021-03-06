#!/usr/bin/env python
##
##  Whabapp - A Web application microframework
##
##  usage: $ python app.py -s localhost 8080
##
import sys
import re
import cgi

STATUS_CODE = {
    100: 'Continue',
    101: 'Switching Protocols',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    306: 'Reserved',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    }

# quote HTML metacharacters.
def q(s):
    assert isinstance(s, basestring), s
    return (s.
            replace('&','&amp;').
            replace('>','&gt;').
            replace('<','&lt;').
            replace('"','&#34;').
            replace("'",'&#39;'))

# encode as a URL.
URLENC = re.compile(r'[^a-zA-Z0-9_.-=]')
def urlenc(url, codec='utf-8'):
    def f(m):
        return '%%%02X' % ord(m.group(0))
    return URLENC.sub(f, url.encode(codec))

# remove redundant spaces.
RMSP = re.compile(r'\s+', re.U)
def rmsp(s):
    return RMSP.sub(' ', s.strip())

# merge two dictionaries.
def mergedict(d1, d2):
    d1 = d1.copy()
    d1.update(d2)
    return d1

# iterable
def iterable(obj):
    return hasattr(obj, '__iter__')

# closable
def closable(obj):
    return hasattr(obj, 'close')


##  Template
##
class Template(object):

    debug = 0

    def __init__(self, *args, **kwargs):
        if '_copyfrom' in kwargs:
            _copyfrom = kwargs['_copyfrom']
            objs = _copyfrom.objs
            kwargs = mergedict(_copyfrom.kwargs, kwargs)
        else:
            objs = []
            for line in args:
                i0 = 0
                for m in self._VARIABLE.finditer(line):
                    objs.append(line[i0:m.start(0)])
                    x = m.group(1)
                    if x == '$':
                        objs.append(x)
                    else:
                        objs.append(self.Variable(x[0], x[1:-1]))
                    i0 = m.end(0)
                objs.append(line[i0:])
        self.objs = objs
        self.kwargs = kwargs
        return

    def __call__(self, **kwargs):
        return self.__class__(_copyfrom=self, **kwargs)

    def __iter__(self):
        return self.render()

    def __repr__(self):
        return '<Template %r>' % self.objs

    def __str__(self):
        return ''.join(self)

    @classmethod
    def load(klass, lines, **kwargs):
        template = klass(*lines, **kwargs)
        if closable(lines):
            lines.close()
        return template
    
    def render(self, codec='utf-8', **kwargs):
        kwargs = mergedict(self.kwargs, kwargs)
        def render1(value, quote=False):
            if value is None:
                pass
            elif isinstance(value, Template):
                if quote:
                    if 2 <= self.debug:
                        raise ValueError
                    elif self.debug:
                        yield '[ERROR: Template in a quoted context]'
                else:
                    for x in value.render(codec=codec, **kwargs):
                        yield x
            elif isinstance(value, dict):
                if 2 <= self.debug:
                    raise ValueError
                elif self.debug:
                    yield '[ERROR: Dictionary included]'
            elif isinstance(value, basestring):
                if quote:
                    yield q(value)
                else:
                    yield value
            elif callable(value):
                for x in render1(value(**kwargs), quote=quote):
                    yield x
            elif iterable(value):
                for obj1 in value:
                    for x in render1(obj1, quote=quote):
                        yield x
            else:
                if quote:
                    yield q(unicode(value))
                else:
                    if 2 <= self.debug:
                        raise ValueError
                    elif self.debug:
                        yield '[ERROR: Non-string object in a non-quoted context]'
            return
        for obj in self.objs:
            if isinstance(obj, self.Variable):
                k = obj.name
                if k in kwargs:
                    value = kwargs[k]
                elif k in self.kwargs:
                    value = self.kwargs[k]
                else:
                    yield '[notfound:%s]' % k
                    continue
                if obj.type == '(':
                    for x in render1(value, quote=True):
                        yield x
                    continue
                elif obj.type == '[':
                    yield urlenc(value)
                    continue
            else:
                value = obj
            for x in render1(value):
                yield x
        return

    _VARIABLE = re.compile(r'\$(\(\w+\)|\[\w+\]|<\w+>)')
    
    class Variable(object):
        
        def __init__(self, type, name):
            self.type = type
            self.name = name
            return
        
        def __repr__(self):
            if self.type == '(':
                return '$(%s)' % self.name
            elif self.type == '[':
                return '$[%s]' % self.name
            else:
                return '$<%s>' % self.name
    

##  Router
##
class Router(object):
    
    def __init__(self, method, regex, func):
        self.method = method
        self.regex = regex
        self.func = func
        return

    @staticmethod
    def make_wrapper(method, pat):
        regex = re.compile('^'+pat+'$')
        def wrapper(func):
            return Router(method, regex, func)
        return wrapper

def GET(pat): return Router.make_wrapper('GET', pat)
def POST(pat): return Router.make_wrapper('POST', pat)


##  Response
##
class Response(object):

    def __init__(self, status_code=200, content_type='text/html', **kwargs):
        self.status_code = status_code
        self.headers = [('Content-Type', content_type)]+kwargs.items()
        return

    def add_header(self, k, v):
        self.headers.append((k, v))
        return

class Redirect(Response):

    def __init__(self, location):
        Response.__init__(self, 302, Location=location)
        return

class NotFound(Response):

    def __init__(self):
        Response.__init__(self, 404)
        return

class InternalError(Response):

    def __init__(self):
        Response.__init__(self, 500)
        return


##  WebApp
##
class WebApp(object):

    debug = 0
    codec = 'utf-8'
    
    def run(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        fp = environ.get('wsgi.input')
        fields = cgi.FieldStorage(fp=fp, environ=environ)
        result = None
        for attr in dir(self):
            router = getattr(self, attr)
            if not isinstance(router, Router): continue
            if router.method != method: continue
            m = router.regex.match(path)
            if m is None: continue
            params = m.groupdict().copy()
            params['_path'] = path
            params['_fields'] = fields
            params['_environ'] = environ
            code = router.func.func_code
            args = code.co_varnames[:code.co_argcount]
            kwargs = {}
            for k in args[1:]:
                if k in fields:
                    kwargs[k] = fields.getvalue(k)
                elif k in params:
                    kwargs[k] = params[k]
            try:
                result = router.func(self, **kwargs)
            except TypeError:
                if 2 <= self.debug:
                    raise
                elif self.debug:
                    result = [InternalError()]
            break
        if result is None:
            result = self.get_default(path, fields, environ)
        elif not iterable(result):
            result = [result]
        for obj in result:
            if isinstance(obj, Response):
                status = '%d %s' % (obj.status_code, STATUS_CODE[obj.status_code])
                start_response(status, obj.headers)
            elif isinstance(obj, Template):
                for x in obj.render(codec=self.codec):
                    if isinstance(x, unicode):
                        x = x.encode(self.codec)
                    yield x
            else:
                if isinstance(obj, unicode):
                    obj = obj.encode(self.codec)
                yield obj
        return

    def get_default(self, path, fields, environ):
        return [NotFound(), '<html><body>not found</body></html>']


# run_server
def run_server(host, port, app):
    from wsgiref.simple_server import make_server
    print >>sys.stderr, 'Serving on %r port %d...' % (host, port)
    httpd = make_server(host, port, app.run)
    httpd.serve_forever()

# run_cgi
def run_cgi(app):
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(app.run)

# run_httpcgi: for cgi-httpd
def run_httpcgi(app):
    from wsgiref.handlers import CGIHandler
    class HTTPCGIHandler(CGIHandler):
        def start_response(self, status, headers, exc_info=None):
            protocol = self.environ.get('SERVER_PROTOCOL', 'HTTP/1.0')
            sys.stdout.write('%s %s\r\n' % (protocol, status))
            return CGIHandler.start_response(self, status, headers, exc_info=exc_info)
    HTTPCGIHandler().run(app.run)

# main
def main(app, argv):
    import getopt
    def usage():
        print 'usage: %s [-d] [-s] [host [port]]' % argv[0]
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'ds')
    except getopt.GetoptError:
        return usage()
    server = False
    debug = 0
    for (k, v) in opts:
        if k == '-d': debug += 1
        elif k == '-s': server = True
    Template.debug = debug
    WebApp.debug = debug
    if server:
        host = ''
        port = 8080
        if args:
            host = args.pop(0)
        if args:
            port = int(args.pop(0))
        run_server(host, port, app)
    else:
        run_cgi(app)
    return


##  Sample App
##
class SampleApp(WebApp):

    @GET('/')
    def index(self):
        yield Response()
        yield Template('<html><body><p>index')
        return
    
    @GET('/hello/(?P<name>.+)')
    def hello(self, name):
        yield Response()
        yield Template('<html><body><p>hello $(name)', name=name)
        return
    
    @GET('/search')
    def search(self, q):
        yield Response()
        yield Template('<html><body>'
                       '<h1>Search results for "$(q)"</h1>',
                       q=q)
        return

if __name__ == '__main__': sys.exit(main(SampleApp(), sys.argv))
