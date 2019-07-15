# Release Notes

## 2.7.0
- Renamed BodeAnalyzer to FrequencyResponseAnalyzer.
- FrequencyResponseAnalyzer
    - can set phase difference between outputs
    - can demodulate at up to 15th harmonic
- minor bug fixes

## 2.6.0
- Update for Moku:Lab firmware version 1.8 (501)
- minor bug fixes

## 2.3.0
### Headlines
- Added **new** instrument support for the **FIR Filter Box**:
	- Build FIR filters with sample rates of up to 15 MS/s.
	- Create arbitrary impulse responses by loading up to 14,000 custom coefficients.
	- 2 input channels, 2 output channels with control matrix for blending inputs.
- Added advanced triggering option for the Oscilloscope:
	- Max/min pulse width
- Added advanced output triggering options to the Arbitrary Waveform Generator, including:
	- Trigger type (edge, pulse-width)
	- Trigger source (ADCs, external)
	- Triggered output modes (single, continuous)
	- Triggered output duration
- Support for data logging instruments to log directly to MATLAB (`.mat`) and NumPy (`.npy`) file types
- Simplified pip pymoku installation process
	- Removed various library dependencies
	- `moku_convert` command-line conversion tool falls back to slower Python implementation without `liquidreader` C-library installed.
- Network packets are now encrypted
- Latest Moku:Lab instrument files and firmware can now be downloaded and installed via the `moku` command line tool for easier device updating, e.g:
	- `moku update fetch`
	- `moku --serial=123456 update install`

### API Changes
- `Moku.deploy_or_connect(...)` and `Moku.deploy_instrument(...)` now have matching API (i.e., input parameters and return value). **Note:** this does not imply identical behaviour (see API documentation).
- `IIRFilterBox` instrument class functions have been changed to match `FIRFilter` API.
	- `set_offset_gain` renamed to `set_gains_offsets` and now only configures the input/output offsets and gains of a specified filter channel.
	- `set_control_matrix` function added to configure input signal mixing gain coefficients.
	- Updated various input parameter ranges including +-1.0V input offset, and +-2.0V output offset.
- Class documentation of various instruments updated.

### Bug Fixes
- IIR Filter outputs are scaled correctly
- Waveform Generator DAC trigger thresholds set correctly
- Oscilloscope and Datalogger instruments correctly log Channel 2 to CSV
- Python 3 fixes:
	- `Moku.list_mokus()` runs without error

### Known Issues
- `LockInAmp.set_outputs` does not change output signal for all selections.

## 2.2.1
### Bug Fixes

- All discovery protocols now work for Python 3
- Moku:PID Differentiator saturation now works correctly when the double-integrator is enabled
- Manually-installable pip package was missing build files

## 2.2.0
### Headlines

- Full support for all instruments, including for the first time:
	- Bode Analyser
    - Filter Box
    - Arbitrary Waveform Generator
    - PID Controller
- New phase-locked output for Phasemeter
- New triggering on Waveform Generator

### API Changes

- All objects and functions now follow US Spelling conventions; e.g. SpectrumAnalyser → SpectrumAnalyzer.

### Known Issues

- The Moku.list_mokus() discovery function doesn't work on Python 3
- The PID Controller differentiator saturation and double-integrator have an unexpected (buggy) interaction, it's recommended to only use on of these features at a time.

## 2.1.3
### Bug Fixes

- Fixed Oscilloscope embedded waveform generator instance reference

## 2.1.2
### Bug Fixes

- Python 3 syntax error

## 2.1.1
### Bug Fixes

- Documentation updates only

## 2.1.0
### Headlines

- New support for:
	- Lock-in Amplifier
	- Bode Analyser
- Numerous bug fixes

### API Changes
- Signal Generator renamed Waveform Generator
	- This is for consistency with documentation and other releases.  The class name has changed, please update your scripts.
- Oscilloscope triggering hysteresis cannot be explicitly set in volts.
	- Complexities with the DSP meant this was always buggy. Hysteresis can now just be turned on and off, toggled between values that are used in the iPad and other clients to implement noise rejection.
- Removed 'upload' parameter from start_data_log.
	- This parameter never worked well, the user should call the instrument's upload function after log completion.
- The meaning of Phasemeter rate flags has been re-defined.
	- 'fast' and 'slow' have been replaced with 'fast', 'medium' and 'slow', representing approximately 1.9ksps, 120sps and 30sps output rate respectively.
### Bug Fixes

- Hysteresis voltage was not correctly set
- Spectrum Analyser gain corrections were slightly wrong
- Data logger now enforces a minimum sample rate rather than just crashing on low rates
- pymoku couldn't be installed on Windows through pip
- autocommit sometimes stopped working if a function through an exception
- numerous compatibility issues with Python 3 rectified
- numerous parameter bounds checks made more explicit and the error messages more helpful
- numerous documentation fixes

### Known Issues
- Doesn't support all released instruments
- Only the iPad can currently be used for PID Controller
- pymoku cannot update Moku:Lab firmware
	- In order to ensure correct functionality of your device, you should use an iPad to check that your Moku:Lab's firmware is up to date when you upgrade your pymoku version. Some pymoku 2.1 functionality may not work unless you use your iPad to update said firmware.
- pymoku Datalogger will not warn if you are about to log a file larger than the maximum file size supported by your SD Card.
	- Most SD cards have a 4GB maximum file size due to limitations of the FAT32 filesystem. If you try and log a file that will exceed that, pymoku will allow it to start but will error-out after it has reached the 4GB limit.
- Waveform Generator output voltages assume a 50-Ohm load
	- pymoku cannot be told what load you're placing on the output, and therefore assumes the common case of 50-ohm. Due to the Moku:Lab's internal 50 ohm series termination, this means that a high impedance load may see at much as twice the requested voltage on the output.
## 2.0.5
### Headlines

- First public release. Support for:
	- Oscilloscope
	- Data Logger
	- Spectrum Analyser
	- Phasemeter
	- Signal Generator

### API Changes

- None

### Bug Fixes

- None

### Known Issues
- Can't install through pip on Windows
- Please use the Anaconda installer instead
- Doesn't support all released instruments
	- Only the iPad can currently be used for Lock-in amplifier, Bode Analyser and PID Controller