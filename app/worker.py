import logging,time
from .main import initialize,db
from .notifications import run_once
def main():
    initialize()
    while True:
        try:run_once(db)
        except Exception as e:logging.error('Notification worker cycle failed (%s)',type(e).__name__)
        time.sleep(30)
if __name__=='__main__':main()
