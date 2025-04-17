import logging
from time import sleep

from gator.adapters.logging import GatorHandler


if __name__ == "__main__":
    logging.basicConfig(
        level="NOTSET",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[GatorHandler()],
    )
    log = logging.getLogger("log_test")
    log.debug("A debug message!")
    sleep(1)
    log.getChild("a.b.c.d").info("Hello world!")
    sleep(1)
    for idx in range(30):
        log.getChild("b").info(f"Pass {idx}")
        sleep(0.2)
    log.getChild("c").warning("A warning message!")
    sleep(1)
    log.error("An error message!")
    sleep(1)
    log.info("DONE")
