#
# pymoku example: Livestream Datalogger
#
# This example demonstrates how you can use the Datalogger to live-stream
# dual-channel voltage data over the network.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import Datalogger

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    # Deploy the Datalogger to your Moku
    i = m.deploy_or_connect(Datalogger)

    # 10Hz sample rate
    i.set_samplerate(10)

    # Stop a previous session, if any, then start a new dual-channel data stream in real
    # time over the network.
    i.stop_stream_data()
    i.start_stream_data(duration=10, ch1=True, ch2=True)

    while True:
        # Get 10 samples off the network at a time
        samples = i.get_stream_data(n=10)

        # Break out of this loop if we received no samples
        # This denotes the end of the streaming session
        if not any(samples): break

        # Print out the new samples
        print("Received: Channel 1 (%d smps), Channel 2 (%d smps)" % (len(samples[0]),len(samples[1])))

    # Denote that we are done with the data streaming session so resources may be cleand up
    i.stop_stream_data()

except StreamException as e:
    print("Error occured: %s" % e)
finally:
    # Close the connection to the Moku to release network resources
    m.close()
