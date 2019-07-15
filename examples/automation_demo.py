#
# pymoku example: Automated Test Demonstration Script
#
# This script demonstrates how the Moku could be utilised in an
# automated test application.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import Oscilloscope, SpectrumAnalyzer
from pymoku import _utils

from automation_demo_helpers import calculate_risetime, calculate_linewidth

# Plotting libraries
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

# For generation of randomised input signals
import numpy.random as rand

import time
import csv

#####################################################################
#
#                   Automated Measurement Script
#
#                           Main sequence
#
#####################################################################

def main():

    print("Beginning automated testing sequence")

    # Connect to the Moku device by name
    moku = Moku.get_by_name('Moku')

    try:
        # Run Phase 1 - Rise Times
        res1, fails1, criteria1 = phase1(moku)

        # Run Phase 2 - Line Widths
        res2, fails2, criteria2 = phase2(moku)

        generate_results_file(moku, res1, fails1, criteria1, res2, fails2, criteria2)

        print("Testing complete")
    finally:
        moku.close()

#####################################################################
#
#                           Testing Phases
#
# This section defines controls for each of the automated testing phases
#
#####################################################################


#####################################################################
#                       PHASE 1 - RISE TIMES
#####################################################################
def phase1(moku):
    print("Beginning Phase 1 - Rise Time")

    # Pre-define simulated signal parameters (for demonstration purposes)
    # --------------------------------------------------------------
    square_frequency = 1e3
    square_amplitude = 0.3
    square_risetime = 0.1 # 10% of cycle
    square_risetime_deviation = 0.1 # +10% of cycle
    # --------------------------------------------------------------

    # Define PASS/FAIL criteria for rise-time
    # ----------------------------------------------
    # For demonstration purposes we set the pass/fail risetime criteria to be a function of the
    # simulated square wave period. This is so we can see examples of 'failed' tests.
    risetime_maximum = 0.18 * (1.0/square_frequency) # 18% of cycle

    # Set up and configure the Oscilloscope instrument
    # --------------------------------------------------------------
    # Prepare an Oscilloscope instrument
    osc = Oscilloscope()

    # Deploy the Oscilloscope to the Moku
    moku.deploy_instrument(osc)

    # Set the data source of Channel 1 to view the generated output sinewave
    osc.set_source(1, 'in1')
    # Set to trigger on Channel 1, rising edge 0V
    osc.set_trigger('out1', 'rising', 0.0)
    # Set timebase +- 1usec
    osc.set_timebase(-1.0/square_frequency/4.0,1.0/square_frequency/4.0)

    # Generate an initial simulation signal
    osc.gen_squarewave(1, square_amplitude, square_frequency, risetime=square_risetime)

    # Set up a plot window for measurement preview
    # --------------------------------------------------------------
    f, ax1, ax2 = phase1_plot_setup()

    # Start taking measurements
    # ---------------------------------------------
    # How many measurements will we take?
    number_of_measurements = 30

    # Prepare lists to hold our measurement results and information of failed tests
    results = []
    fails = []
    risetimes = []

    # This variable tracks the ID of the current waveform data
    waveformid = 0
    # This loop continuously retrieves waveform data and calculates associated rise times from it
    for i in range(number_of_measurements):

        # Print a message to denote progress of this testing phase
        #print("Measurement #%d/%d" % (i+1,number_of_measurements))

        # Get new waveform data (ensuring it is unique to the last)
        data = osc.get_realtime_data(timeout=5)
        while data.waveformid <= waveformid:
            time.sleep(0.05)
            data = osc.get_realtime_data(timeout=10)
        waveformid = data.waveformid

        # Simulate the next signal now while we process the current data (speeds up performance)
        # We simulate a signal with "noisy" risetime by generating a square wave
        # with a randomised rise time
        random_risetime = square_risetime + rand.random()*square_risetime_deviation
        osc.gen_squarewave(1, square_amplitude, square_frequency, risetime=random_risetime)

        # Calculate the risetime of this new waveform data
        risetime = calculate_risetime(data.ch1, data.time)

        # Determine if this test passed by comparing the calculated risetime to pass criteria
        passed = (risetime < risetime_maximum)

        # Record the results
        results.append({'id': i, 'risetime': risetime, 'passed': passed }) # msec
        risetimes.append(risetime)

        # If this test did not pass, record all data for post-analysis
        if not passed:
            fails.append({'id': i, 'data': data.ch1, 'time': data.time, 'risetime' : risetime })

        # Update the plot with new data
        progress = ((i+1)/float(number_of_measurements)) * 100
        phase1_plot_update(f, ax1, ax2, data, passed, risetimes, fails, risetime_maximum, progress)


    plt.close()

    return results, fails, risetime_maximum

#####################################################################
#                       PHASE 2 - LINE WIDTH
#####################################################################
def phase2(moku):
    print("Beginning Phase 2 - Line Width")

    # Pre-define simulated signal parameters (for demonstration purposes)
    # --------------------------------------------------------------
    sine_frequency = 15e6
    sine_amplitude = 1.0
    # --------------------------------------------------------------

    # Define PASS/FAIL criteria for linewidth
    # ----------------------------------------------
    # This has been tuned for the demonstration so we occassionally see failed tests
    linewidth_maximum = 3.0e3 # Hz


    # Set up and configure the Spectrum Analyzer instrument
    # --------------------------------------------------------------
    # Prepare a Spectrum Analyzer instrument
    specan = SpectrumAnalyzer()

    # Deploy the Spectrum Analyzer to the Moku
    moku.deploy_instrument(specan)

    # Set +- 0.1MHz span around simulated signal frequency
    specan.set_span(sine_frequency - 0.1e6, sine_frequency + 0.1e6)
    # Set voltage scale to be in dBm
    specan.set_dbmscale(True)

    # Generate the simulation signal
    specan.gen_sinewave(1, 1.0, sine_frequency)

    # Set on-device averaging of 8 FFTs
    specan.waveform_avg1 = 3
    specan.waveform_avg2 = 3
    specan.commit()

    # Set up a plot window for measurement preview
    # --------------------------------------------------------------
    f, ax1 = phase2_plot_setup()

    # Start taking measurements
    # ---------------------------------------------
    # How many measurements will we take?
    number_of_measurements = 30

    # Prepare lists to hold our measurement results and information of failed tests
    results = []
    fails = []
    linewidths = []

    # This variable tracks the ID of the current waveform data
    waveformid = 0

    # This loop continuously retrieves spectrum data and calculates associated linwewidth from it
    for i in range(number_of_measurements):

        # Get new spectrum data (ensuring it is unique to the last)
        data = specan.get_data(timeout=10)
        while data.waveformid <= waveformid:
            time.sleep(0.05)
            data = specan.get_data(timeout=10)
        waveformid = data.waveformid

        # Find the peak and calculate the linewidth of this new spectrum data
        linewidth, peak, hf1, hf2 = calculate_linewidth(data.ch1, data.frequency)

        # Determine if this test passed by comparing the calculated linewidth to pass criteria
        passed = linewidth < linewidth_maximum

        # Record the results
        linewidths.append(linewidth)
        results.append({'id': i, 'linewidth': linewidth, 'passed': passed})

        # If this test did not pass, record all data for post-analysis
        if not passed:
            fails.append({'id': i, 'data': data.ch1, 'frequency': data.frequency, 'linewidth' : linewidth,
                'peak': peak, 'half_f1': hf1, 'half_f2': hf2 })

        progress = ((i+1)/float(number_of_measurements)) * 100
        phase2_plot_update(f, ax1, data, passed, peak, hf1, hf2, progress)

    plt.close()

    return results, fails, linewidth_maximum

#####################################################################
#
#                       Results File Generator
#
#####################################################################

def generate_results_file(moku, results1, fails1, criteria1, results2, fails2, criteria2):
    from datetime import datetime
    logname = datetime.now().strftime("AutomatedTest_Moku{}_%Y%m%d_%H%M%S.csv".format(moku.serial))
    ts = _utils.formatted_timestamp()

    with open(logname, 'w') as file:
        writer = csv.DictWriter(file, fieldnames=['id','risetime','passed'])
        file.write("% Automated Test Run\n%")
        file.write(" %s\n" % ts)
        file.write("% -------------------------------------\n")
        file.write("% PHASE 1 - RISE TIME\n")
        file.write("%% Pass Criteria: %f sec \n" % criteria1)
        file.write("%% Failed: %d / %d\n" % (len(fails1), len(results1)))
        file.write("% -------------------------------------\n")

        file.write('Test ID, Risetime (sec), Passed\n')
        for r in results1:
            writer.writerow(r)

        writer = csv.DictWriter(file, fieldnames=['id','linewidth','passed'])
        file.write("% -------------------------------------\n")
        file.write("% PHASE 2 - LINE WIDTH\n")
        file.write("%% Pass Criteria: %f Hz\n" % criteria2)
        file.write("%% Failed: %d / %d\n" % (len(fails2), len(results2)))
        file.write("% -------------------------------------\n")

        file.write('Test ID, Linewidth (Hz), Passed\n')
        for r in results2:
            writer.writerow(r)

        file.close()

    print("Generated log file: %s" % logname)


#####################################################################
#
#                       Plotting Helpers
#
#####################################################################

def phase1_plot_setup():
    # Set up a 1x2 plot
    f, (ax1, ax2) = plt.subplots(1,2)
    f.suptitle('Phase 1 - Rise Times', fontsize=18, fontweight='bold')

    # Choose a colour palette and font size/style
    colours = sns.color_palette("muted")
    sns.set_context('poster')

    # Maximise the plotting window
    plot_backend = matplotlib.get_backend()
    mng = plt.get_current_fig_manager()
    if plot_backend == 'TkAgg':
        mng.resize(*mng.window.maxsize())
    elif plot_backend == 'wxAgg':
        mng.frame.Maximize(True)
    elif plot_backend == 'Qt4Agg':
        mng.window.showMaximized()

    return f, ax1, ax2

def phase1_plot_update(f, ax1, ax2, data, passed, results, fails, failure_criteria, progress):
        ax1.cla()
        ax2.cla()
        sns.tsplot(data.ch1, time=data.time, color="g" if passed else "r", ax=ax1, interpolate=True)
        if len(results) > 1:
            try:
                sns.distplot(results, norm_hist=False, rug=True, ax=ax2)
            except Exception:
                pass
        ax1.set(title='Transition Waveform', xlabel='Time (sec)', ylabel='Amplitude (V)')
        ax2.set(title="Risetime Histogram", ylabel="Density", xlabel="Risetime (sec)")
        ax2.annotate('Outside Spec: %d / %d\nCompleted %d%%' % (len(fails), len(results), progress), xy=(0.75,0.90), xycoords='axes fraction', fontsize=14)
        xlims = ax2.get_xlim()
        ax2.axvspan(failure_criteria,xlims[1] - 0.001*(xlims[1] - xlims[0]), alpha=0.1, color='red')
        plt.pause(0.01)

def phase2_plot_update(f, ax1, data, passed, peak, hf1, hf2, progress):
        # Update the plot with latest measurement
        ax1.cla()
        freq_mhz = map(lambda x: x/1e6, data.frequency)
        sns.tsplot(data.ch1, time=freq_mhz, ax=ax1, interpolate=True)
        ax1.plot(peak[0]/1e6, peak[1], 'v')
        ax1.set(title='Beatnote Spectrum', xlabel='Frequency (MHz)', ylabel='Power (dBm)')
        ax1.annotate('Peak (%.2f MHz)\nLinewidth (%.2f kHz)\nCompleted %d%%' % (peak[0]/1e6, (hf2[0]-hf1[0])/1e3, progress), xy=(0.80,0.90), xycoords='axes fraction', fontsize=14)
        ax1.axvspan(hf1[0]/1e6,hf2[0]/1e6, alpha=0.1, color='green' if passed else 'red')
        plt.pause(0.01)

def phase2_plot_setup():
    # Set up a 1x1 plot
    f, ax1 = plt.subplots(1, 1)
    f.suptitle('Phase 2 - Line Width', fontsize=18, fontweight='bold')

    # Choose a colour palette and font size/style
    colours = sns.color_palette("muted")
    sns.set_context('poster')

    # Maximise the plotting window
    plot_backend = matplotlib.get_backend()
    mng = plt.get_current_fig_manager()
    if plot_backend == 'TkAgg':
        mng.resize(*mng.window.maxsize())
    elif plot_backend == 'wxAgg':
        mng.frame.Maximize(True)
    elif plot_backend == 'Qt4Agg':
        mng.window.showMaximized()

    return f, ax1

if __name__=='__main__':
    main()
