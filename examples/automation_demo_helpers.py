#
# (c) 2019 Liquid Instruments Pty. Ltd.
#

import numpy as np
import warnings

warnings.filterwarnings("ignore")

def calculate_risetime(amplitude_data, time_data):
    """
        A helper function which calculates an approximation to waveform
        rise time.

        For demonstration purposes only.
    """

    # Determine the waveform amplitude differential
    min_val = min(amplitude_data)
    max_val = max(amplitude_data)
    diff = max_val - min_val

    # Find an approximate start/end point of the waveform rise
    # by looking for points of 1% and 99% amplitude.
    low_thresh = min_val + 0.02*diff
    high_thresh = max_val - 0.02*diff
    i_low = [n for n,i in enumerate(amplitude_data) if i > low_thresh][0]
    i_high = [n for n,i in enumerate(amplitude_data) if i > high_thresh][0]

    # The time difference between the end points is approximately the rise time
    return time_data[i_high] - time_data[i_low]

def calculate_linewidth(power_data, frequency_data):
    """
        A helper function which calculates an approximation to spectrum
        line width.

        For demonstration purposes only.
    """

    # Find the peak
    peak_index = np.argmax(power_data)
    peak_amp = power_data[peak_index]
    peak_freq = frequency_data[peak_index]

    hist, bins = np.histogram(power_data, bins=10)
    snr_index = np.argmax(hist)
    snr = (bins[snr_index] + bins[snr_index+1]) / 2.0

    half_amp = ((peak_amp - snr)/2.0) + snr

    # Find the half-amplitude frequencies
    half_peak_data = map(lambda x: x - half_amp, power_data)
    half_peak_crossings = np.where(np.diff(np.sign(half_peak_data)))[0]

    half_freq1 = frequency_data[half_peak_crossings[0]+1]
    half_freq2 = frequency_data[half_peak_crossings[-1]]

    width = half_freq2 - half_freq1

    return width, (peak_freq, peak_amp), (half_freq1, half_amp), (half_freq2, half_amp)
