
def build_rest_namespace(base, owner=None, app=None):
    if owner and app:
        p = (base, "servicesNS", owner, app)
    elif app:
        p = (base, "servicesNS", "nobody", app)
    elif owner:
        raise ValueError("Can't specify user without app!")
    else:
        p = (base, "services")
    return "/".join(p)

def build_rest_url(base, service, owner=None, app=None):
    prefix = build_rest_namespace(base, owner, app)
    return prefix + "/" + service


'''
### DELETE ALL THIS STUFFF    SWITCHING TO SPLUNK-SDK

class SplunkRestException(Exception):
    pass

class SplunkRestLoginException(SplunkRestException):
    pass


class SplunkRestHelper(object):
    def __init__(self, url):
        from requests import Session
        self.url = url
        self._service = Session()
        self._session_key = None

    def set_verify(self, verify):
        if not verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            #import warnings
            #warnings.filterwarnings("drop", category="InsecureRequestWarning")
        self._service.verify = verify

    def login(self, username, password):
        url = build_rest_url(self.url, "auth/login")
        data = {
            "username": username,
            "password": password,
            "output_mode": "json"
        }
        resp = self._service.request("POST", url, data=data)
        if resp.status_code > 400:
            raise SplunkRestLoginException("Login failure for {}\n".format(username))
        self._session_key = resp.json()["sessionKey"]

    def set_sessionkey(self, key):
        self._session_key = key

    def _request(self, method, url, data=None, headers=None, **kwargs):
        if data is None:
            data = {}
        if headers is None:
            headers = {}
        ' ' '
        #if "headers" not is kwargs or kwargs["headers"] is  None:
        #    kwargs["headers"] = {}
        #if "data" not in kwargs or kwargs["data"] is  None:
        #    kwargs["data"] = {}
        #headers = kwargs["headers"]
        #data = kwargs["data"]
        ' ' '
        headers["Authorization"] = "Splunk {}".format(self._session_key)
        data["output_mode"] = "json"
        req = self._service.request(method, url, headers=headers, data=data, **kwargs)
        return req
        #return (req.status_code, req.json())

    def get_entity(self, entity, owner=None, app=None):
        url = build_rest_url(self.url, entity, owner, app)
        resp = self._request("GET", url)
        #return resp.json()["content"]
        return resp

    def _put_update(self, entity, settings, owner=None, app=None):
        url = build_rest_url(self.url, entity, owner, app)
        resp = self._request("POST", url, data=settings)
        return resp

    def _put_new(self, entity, settings, owner=None, app=None):
        entity, name = entity.rsplit("/", 1)
        url = build_rest_url(self.url, entity, owner, app)
        settings = dict(settings)
        settings["name"] = name
        resp = self._request("POST", url, data=settings)
        return resp

    def put_entity(self, entity, settings, owner=None, app=None, assume="update"):
        if assume == "update":
            r = self._put_update(entity, settings, owner, app)
            if r.status_code != 200:
                r = self._put_new(entity, settings, owner, app)
            return r
        raise AssertionError("Unknown values for assume!")

'''
