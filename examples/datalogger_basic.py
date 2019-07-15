#
# pymoku example: Basic Datalogger
#
# This example demonstrates use of the Datalogger instrument to log time-series
# voltage data to a (Binary or CSV) file.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import Datalogger
import time

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(Datalogger)

    # 100 samples per second
    i.set_samplerate(100)

    # Stop an existing log, if any, then start a new one. 10 seconds of both channels to the
    # SD Card (rather than internal storage). Use the Moku's binary file format for better speed
    # and size performance.
    i.stop_data_log()
    i.start_data_log(duration=10, use_sd=True, ch1=True, ch2=True, filetype='bin')

    # Track progress percentage of the data logging session
    progress = 0
    while progress < 100:
        # Wait for the logging session to progress by sleeping 0.5sec
        time.sleep(0.5)
        # Get current progress percentage and print it out
        progress = i.progress_data_log()
        print("Progress {}%".format(progress))

    # Upload the log file to the local directory
    i.upload_data_log()
    print("Uploaded log file to local directory.")

    # Denote that we are done with the data logging session so resources may be cleand up
    i.stop_data_log()

except StreamException as e:
    print("Error occured: %s" % e)
finally:
    m.close()
