"""Twilio WhatsApp integration — NOT implemented yet.

This is intentionally left minimal. The Twilio webhook is the only
major piece left; when added it becomes just another client of the
existing chat_service, exactly like the admin Test Chat.

Future flow:

    Twilio webhook (incoming WhatsApp message)
      -> identify the receiving number
      -> map that number to a bot_id (a bots.whatsapp_number column
         or a small lookup table would be added for this)
      -> chat_service.ask(bot_id, session_id=from_number, message=body)
      -> send the returned text back via Twilio

No TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN is required for the rest of
the application to run.
"""
