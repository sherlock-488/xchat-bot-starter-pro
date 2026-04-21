"""Chat API client — documented Chat API routes from the XChat migration guide.

Documented endpoints:
  GET  /2/users/{id}/public_keys
  GET  /2/chat/conversations
  GET  /2/chat/conversations/{conversation_id}
  POST /2/chat/conversations/{conversation_id}/messages

All messages on the Chat API are end-to-end encrypted.
Encryption and decryption require chat-xdk (pending stable public release).
This client only handles already-encrypted payloads — it does NOT encrypt anything.
"""

from xchat_bot.chat.api import ChatApiClient

__all__ = ["ChatApiClient"]
