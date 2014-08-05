# -*- coding: utf-8 -*-

# import this module using
# >>> import bitshares_delegate_tools.repl
# to set up a (dummy) flask context to allow you to access the DB

from bitshares_delegate_tools.wsgi import application
ctx = application.app.test_request_context()

import bitshares_delegate_tools.rpcutils as rpc
import bitshares_delegate_tools.core as core

ctx.push()
