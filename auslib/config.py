from ConfigParser import RawConfigParser, NoOptionError
import logging

class AUSConfig(object):
    required_options = {
        'logging': ['logfile'],
        'database': ['dburi']
    }
    # Originally, this was done with getattr(logging, level), but it seems bad
    # to look up, and possibly return, arbitrary keys from a config file so it
    # was replaced with this simple mapping.
    loglevels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    def __init__(self, filename):
        self.cfg = RawConfigParser()
        self.cfg.read(filename)

    def validate(self):
        errors = []
        for section, options in self.required_options.items():
            if not self.cfg.has_section(section):
                errors.append("Missing section '%s'" % section)
            for opt in options:
                if not self.cfg.has_option(section, opt):
                    errors.append("Missing option '%s' from section '%s'" % (opt, section))
        return errors

    def getLogfile(self):
        return self.cfg.get("logging", "logfile")

    def getLogLevel(self):
        try:
            return self.loglevels[self.cfg.get("logging", "level")]
        # NoOptionError is raised when we can't find the level in the config.
        # KeyError is raised when we can't find it in the mapping.
        except (NoOptionError, KeyError):
            return logging.WARNING

    def getDburi(self):
        return self.cfg.get('database', 'dburi')
