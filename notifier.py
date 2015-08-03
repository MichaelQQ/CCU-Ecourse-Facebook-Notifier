#/usr/bin/env python
#-*- coding: utf-8 -*-
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""A barebones AppEngine application that uses Facebook for login.

This application uses OAuth 2.0 directly rather than relying on Facebook's
JavaScript SDK for login. It also accesses the Facebook Graph API directly
rather than using the Python SDK. It is designed to illustrate how easy
it is to use the Facebook Platform without any third party code.

See the "appengine" directory for an example using the JavaScript SDK.
Using JavaScript is recommended if it is feasible for your application,
as it handles some complex authentication states that can only be detected
in client-side code.
"""


import base64
import cgi
import Cookie
import email.utils
import hashlib
import hmac
import logging
import os.path
import time
import urllib
import wsgiref.handlers
import webapp2
#import facebook
import requests
import ecourse

from django.utils import simplejson as json
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template


class User(db.Model):
    id = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    name = db.StringProperty(required=True)
    profile_url = db.StringProperty(required=True)
    access_token = db.StringProperty(required=True)


class BaseHandler(webapp.RequestHandler):
    @property
    def current_user(self):
        """Returns the logged in Facebook user, or None if unconnected."""
        if not hasattr(self, "_current_user"):
            self._current_user = None
            user_id = parse_cookie(self.request.cookies.get("fb_user"))
            if user_id:
                self._current_user = User.get_by_key_name(user_id)
        return self._current_user


class HomeHandler(BaseHandler):
    def get(self):
        #path = os.path.join(os.path.dirname(__file__), "index.html")
        #args = dict(current_user=self.current_user)
        #self.response.out.write(template.render(path, args))
        self.redirect("/auth/login")
    def post(self):
        self.redirect("/auth/login")


class LoginHandler(BaseHandler):
    def post(self):
        self.redirect("/auth/login")
    def get(self):
        verification_code = self.request.get("code")
        args = dict(client_id=FACEBOOK_APP_ID,
                    redirect_uri=self.request.path_url)
        if self.request.get("code"):
            args["client_secret"] = FACEBOOK_APP_SECRET
            args["code"] = self.request.get("code")
            response = cgi.parse_qs(urllib.urlopen(
                FB_GRAPH+"oauth/access_token?" +
                urllib.urlencode(args)).read())
            access_token = response["access_token"][-1]

            # Download the user profile and cache a local instance of the
            # basic profile info
            profile = json.load(urllib.urlopen(
                FB_GRAPH+"me?" + urllib.urlencode(dict(access_token=access_token))))
            user = User(
                        key_name=str(profile["id"]), id=str(profile["id"]), 
                        name=profile["name"], access_token=access_token, 
                    profile_url=profile["link"])
            user.put()
            set_cookie(self.response, "fb_user", str(profile["id"]),
                       expires=time.time() + 30 * 86400)
            self.redirect("/task/sendmsg")
        else:
            self.redirect(FB_GRAPH+"oauth/authorize?" + urllib.urlencode(args))


class LogoutHandler(BaseHandler):
    def get(self):
        try:
            delete_db_user(self.current_user.id)
            set_cookie(self.response, "fb_user", "", expires=time.time() - 86400)
        except:
            print 'Could not Logout'
        finally:
            #self.redirect("https://www.facebook.com/")
            path = os.path.join(os.path.dirname(__file__), "index.html")
            args = dict(current_user=self.current_user)
            self.response.out.write(template.render(path, args))


class TestHandler(BaseHandler):
    def get(self):
        send_fb_notification(self.current_user.id, u'微積分:6/10 期末成績公佈(2014-04-13)\n各位同學好， 本學期微積分通過人數：1人，歡迎大家下學期再次選修！---此為測試公告')
        send_fb_notification(self.current_user.id, u'系統通知:本系統即將爆炸！---此為測試公告')
        self.redirect("/task/sendmsg")


def delete_db_user(user_id):
    SQL = "SELECT * FROM User WHERE id = '" + user_id + "'"
    q = db.GqlQuery(SQL).get()
    q.delete()


class SendMsgHandler(BaseHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), "send.html")
        args = dict(current_user=self.current_user)
        self.response.out.write(template.render(path, args))
    def post(self):
        ecourse_id = self.request.get('ecourse_id')
        ecourse_pd = self.request.get('ecourse_pd')
        ANNOUNCE_LIST = ecourse.get_announcements(ecourse_id, ecourse_pd)
        if ANNOUNCE_LIST == 'Error in get_announcements':
            print 'Error in get_announcements'
        else:
            for ANNOUNCE in ANNOUNCE_LIST:
                if len(ANNOUNCE) > 150:
                    MESSAGE = ANNOUNCE[:150] + '(message too long...)'
                else:
                    MESSAGE = ANNOUNCE
                send_fb_notification(self.current_user.id, MESSAGE)
        self.redirect("/task/sendmsg")


def send_fb_notification(user_id, message):
    #Request the app token needed by notification api
    args = dict(client_id=FACEBOOK_APP_ID, 
                client_secret=FACEBOOK_APP_SECRET, 
                grant_type='client_credentials')
    response = cgi.parse_qs(urllib.urlopen(
            FB_GRAPH+"oauth/access_token?" +
            urllib.urlencode(args)).read())
    app_token = response["access_token"][-1]
    URL = FB_GRAPH + str(user_id) + "/notifications?" + urllib.urlencode(
            dict(access_token=app_token, template=message.encode('utf-8')))
    r = requests.post(URL)


def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    timestamp = str(int(time.time()))
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if domain:
        cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(
            expires, localtime=False, usegmt=True)
    #response.headers._headers.append(("Set-Cookie", cookie.output()[12:]))
    response.headers.add('Set-Cookie', cookie.output()[12:])


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value:
        return None
    parts = value.split("|")
    if len(parts) != 3:
        return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - 30 * 86400:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None


def cookie_signature(*parts):
    """Generates a cookie signature.

    We use the Facebook app secret since it is different for every app (so
    people using this example don't accidentally all use the same secret).
    """
    hash = hmac.new(FACEBOOK_APP_SECRET, digestmod=hashlib.sha1)
    for part in parts:
        hash.update(part)
    return hash.hexdigest()

app = webapp2.WSGIApplication([
        (r"/", LoginHandler),#HomeHandler),
        (r"/auth/login", LoginHandler),
        #(r"/auth/logout", LogoutHandler),
        (r"/task/sendmsg", SendMsgHandler),
        (r"/test", TestHandler),
    ])
