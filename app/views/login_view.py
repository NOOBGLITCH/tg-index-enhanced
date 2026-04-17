import hmac
import time

from aiohttp import web
import aiohttp_jinja2
from aiohttp_session import new_session, get_session

from .base import BaseView


class LoginView(BaseView):
    @aiohttp_jinja2.template("login.html")
    async def login_get(self, req: web.Request) -> web.Response:
        return dict(
            authenticated=False, redirect_to=str(req.query.get("redirect_to", "/"))
        )

    async def login_post(self, req: web.Request) -> web.Response:
        post_data = await req.post()
        redirect_to = post_data.get("redirect_to") or "/"

        if not redirect_to.startswith("/"):
            redirect_to = "/"

        location = req.app.router["login_page"].url_for()
        if redirect_to != "/":
            location = location.update_query({"redirect_to": redirect_to})

        username_input = post_data.get("username", "")
        password_input = post_data.get("password", "")

        if not username_input:
            loc = location.update_query({"error": "Username missing"})
            return web.HTTPFound(location=loc)

        if not password_input:
            loc = location.update_query({"error": "Password missing"})
            return web.HTTPFound(location=loc)

        expected_username = req.app.get("username", "")
        expected_password = req.app.get("password", "")

        username_match = hmac.compare_digest(username_input, expected_username)
        password_match = hmac.compare_digest(password_input, expected_password)
        authenticated = username_match and password_match

        if not authenticated:
            loc = location.update_query({"error": "Wrong Username or Password"})
            return web.HTTPFound(location=loc)

        session = await new_session(req)
        session["logged_in"] = True
        session["logged_in_at"] = time.time()

        return web.HTTPFound(location=redirect_to)


class LogoutView(BaseView):
    async def logout_get(self, req: web.Request) -> web.Response:
        session = await get_session(req)
        session["logged_in"] = False
        session["logged_in_at"] = None

        return web.HTTPFound(req.app.router["home"].url_for())
