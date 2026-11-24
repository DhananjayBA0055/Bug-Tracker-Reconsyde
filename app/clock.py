"""UTC event instants and explicit business dates must not be mixed at midnight."""
import os
from datetime import datetime,timezone
from zoneinfo import ZoneInfo

def business_date(moment=None):
    moment=moment or datetime.now(timezone.utc)
    return moment.astimezone(ZoneInfo(os.environ.get('APP_TIMEZONE','Asia/Kolkata'))).date()
