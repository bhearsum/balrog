from migrate import DatabaseAlreadyControlledError

import logging

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.set_defaults(
        db='sqlite:///update.db',
        port=8000,
    )
    parser.add_option("-d", "--db", dest="db", help="database to use, relative to inputdir")
    parser.add_option("-p", "--port", dest="port", type="int", help="port for server")
    parser.add_option("--host", dest="host", default='127.0.0.1', help="host to listen on. for example, 0.0.0.0 binds on all interfaces.")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
        help="Verbose output")
    options, args = parser.parse_args()

    # Logging needs to get set-up before importing the application
    # to make sure that logging done from other modules uses our Logger.
    from auslib.log import log_format, BalrogLogger

    logging.setLoggerClass(BalrogLogger)
    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format=log_format)

    from auslib.web.base import app, AUS

    AUS.setDb(options.db)
    try:
        AUS.db.create()
    except DatabaseAlreadyControlledError:
        pass

    app.config['SECRET_KEY'] = 'abc123'
    app.config['DEBUG'] = True
    app.run(port=options.port, host=options.host)
