"""
Some methods copied from fastcore.net, which can be used to monkey patch it and raise
an exception if there's a HTTP timeout.
"""
import fastcore.net
import json


timeout_seconds = 10


def urlopen(url, data=None, headers=None, **kwargs):
    "Like `urllib.request.urlopen`, but first `urlwrap` the `url`, and encode `data`"
    if kwargs and not data:
        data = kwargs
    if data is not None:
        if not isinstance(data, (str, bytes)):
            data = fastcore.net.urlencode(data)
        if not isinstance(data, bytes):
            data = data.encode("ascii")
    # print("sdlfsdf")
    return fastcore.net._opener.open(
        fastcore.net.urlwrap(url, data=data, headers=headers), timeout=timeout_seconds
    )


def urlread(
    url,
    data=None,
    headers=None,
    decode=True,
    return_json=False,
    return_headers=False,
    **kwargs,
):
    "Retrieve `url`, using `data` dict or `kwargs` to `POST` if present"
    try:
        with urlopen(url, data=data, headers=headers, **kwargs) as u:
            res, hdrs = u.read(), u.headers
    except fastcore.net.HTTPError as e:
        if 400 <= e.code < 500:
            raise fastcore.net.ExceptionsHTTP[e.code](e.url, e.hdrs, e.fp) from None
        else:
            raise

    if decode:
        res = res.decode()
    if return_json:
        res = json.loads(res)
    return (res, dict(hdrs)) if return_headers else res


def urlsend(
    url,
    verb,
    headers=None,
    route=None,
    query=None,
    data=None,
    json_data=True,
    return_json=True,
    return_headers=False,
    debug=None,
):
    "Send request with `urlrequest`, converting result to json if `return_json`"
    req = fastcore.net.urlrequest(
        url, verb, headers, route=route, query=query, data=data, json_data=json_data
    )
    if debug:
        debug(req)
    return urlread(req, return_json=return_json, return_headers=return_headers)
