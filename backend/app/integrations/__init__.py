"""CRM integrations.

Mirrors ``app.connectors`` deliberately: a base class declaring capabilities, a
registry, and providers that **refuse rather than invent**. The lesson that
shaped the connectors -- four separate places returning plausible numbers when
they could not get real ones -- applies at least as strongly here, because the
data is a customer relationship rather than a like count.
"""
