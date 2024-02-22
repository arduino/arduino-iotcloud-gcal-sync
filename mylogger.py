import logging

def getlogger(modulename):
    logger = logging.getLogger(modulename)
    logger.setLevel(logging.INFO)
    lh=logging.StreamHandler()
    lh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(threadName)s]"))
    logger.addHandler(lh)
    #lh2 = logging.FileHandler("poller.log")
    #lh2.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(threadName)s]"))
    #logger.addHandler(lh2)
    return logger