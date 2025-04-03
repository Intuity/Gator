import logging
from gator.adapters.logging import GatorHandler


if __name__ == "__main__":
    logging.basicConfig(
        level="NOTSET",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[GatorHandler()],
    )
    log = logging.getLogger("log_test")
    log.info("Hello world!")
    log.warning("A warning message!")
    log.error("An error message!")
