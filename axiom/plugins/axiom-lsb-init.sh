#!/bin/sh -x

. /lib/lsb/init-functions

# main()
# start or stop the service
# Several environment variables are expected at this point:
#    PYTHONPATH - should be correct to import everything
#    AXIOMATIC_SCRIPT - points to the appropriate Axiomatic command
#    AXIOMATIC_DATABASE - what directory is the database in

main () {

    # temporary measure to make sure that improperly-placed stuff like
    # batch.log ends up in the right place.

    cd "`dirname $AXIOMATIC_DATABASE`"
    case "$1" in
        start)
            log_begin_msg "Starting axiomatic... "
            "$AXIOMATIC_SCRIPT" -d "$AXIOMATIC_DATABASE" start \
                -u "$AXIOMATIC_UID" -g "$AXIOMATIC_GID"
            log_end_msg $?
            ;;

        stop)
            log_begin_msg "Stopping axiomatic... "
            "$AXIOMATIC_SCRIPT" -d "$AXIOMATIC_DATABASE" stop

            sleep 3s            # remove this line when 'stop' properly blocks
                                # until the pidfile has been removed...
            log_end_msg $?
            ;;

        restart)
            "$0" stop
            "$0" start
            ;;

        status)
            "$AXIOMATIC_SCRIPT" -d "$AXIOMATIC_DATABASE" status
            ;;

        *)
            echo "Usage: $0 <start | stop | restart | status>"
            ;;
    esac
}


