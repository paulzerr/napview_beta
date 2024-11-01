"""Automatic sleep staging of polysomnography data."""

import os
import mne
import glob
import joblib
import logging
import numpy as np
import pandas as pd
import antropy as ant
import scipy.signal as sp_sig
import scipy.stats as sp_stats
import matplotlib.pyplot as plt
from mne.filter import filter_data
from sklearn.preprocessing import robust_scale
from scipy.integrate import simpson

logger = logging.getLogger("yasa")



def bandpower_from_psd(
    psd,
    freqs,
    ch_names=None,
    bands=[
        (0.5, 4, "Delta"),
        (4, 8, "Theta"),
        (8, 12, "Alpha"),
        (12, 16, "Sigma"),
        (16, 30, "Beta"),
        (30, 40, "Gamma"),
    ],
    relative=True,
):
    """Compute the average power of the EEG in specified frequency band(s)
    given a pre-computed PSD.

    .. versionadded:: 0.1.5

    Parameters
    ----------
    psd : array_like
        Power spectral density of data, in uV^2/Hz. Must be of shape (n_channels, n_freqs).
        See :py:func:`scipy.signal.welch` for more details.
    freqs : array_like
        Array of frequencies.
    ch_names : list
        List of channel names, e.g. ['Cz', 'F3', 'F4', ...]. If None, channels will be labelled
        ['CHAN000', 'CHAN001', ...].
    bands : list of tuples
        List of frequency bands of interests. Each tuple must contain the lower and upper
        frequencies, as well as the band name (e.g. (0.5, 4, 'Delta')).
    relative : boolean
        If True, bandpower is divided by the total power between the min and
        max frequencies defined in ``band`` (default 0.5 to 40 Hz).

    Returns
    -------
    bandpowers : :py:class:`pandas.DataFrame`
        Bandpower dataframe, in which each row is a channel and each column a spectral band.
    """
    # Type checks
    assert isinstance(bands, list), "bands must be a list of tuple(s)"
    assert isinstance(relative, bool), "relative must be a boolean"

    # Safety checks
    freqs = np.asarray(freqs)
    assert freqs.ndim == 1
    psd = np.atleast_2d(psd)
    assert psd.ndim == 2, "PSD must be of shape (n_channels, n_freqs)."
    all_freqs = np.hstack([[b[0], b[1]] for b in bands])
    fmin, fmax = min(all_freqs), max(all_freqs)
    idx_good_freq = np.logical_and(freqs >= fmin, freqs <= fmax)
    freqs = freqs[idx_good_freq]
    res = freqs[1] - freqs[0]
    nchan = psd.shape[0]
    assert nchan < psd.shape[1], "PSD must be of shape (n_channels, n_freqs)."
    if ch_names is not None:
        ch_names = np.atleast_1d(np.asarray(ch_names, dtype=str))
        assert ch_names.ndim == 1, "ch_names must be 1D."
        assert len(ch_names) == nchan, "ch_names must match psd.shape[0]."
    else:
        ch_names = ["CHAN" + str(i).zfill(3) for i in range(nchan)]
    bp = np.zeros((nchan, len(bands)), dtype=np.float64)
    psd = psd[:, idx_good_freq]
    total_power = simpson(psd, dx=res)
    total_power = total_power[..., np.newaxis]

    # Check if there are negative values in PSD
    if (psd < 0).any():
        msg = (
            "There are negative values in PSD. This will result in incorrect "
            "bandpower values. We highly recommend working with an "
            "all-positive PSD. For more details, please refer to: "
            "https://github.com/raphaelvallat/yasa/issues/29"
        )
        logger.warning(msg)

    # Enumerate over the frequency bands
    labels = []
    for i, band in enumerate(bands):
        b0, b1, la = band
        labels.append(la)
        idx_band = np.logical_and(freqs >= b0, freqs <= b1)
        bp[:, i] = simpson(psd[:, idx_band], dx=res)

    if relative:
        bp /= total_power

    # Convert to DataFrame
    bp = pd.DataFrame(bp, columns=labels)
    bp["TotalAbsPow"] = np.squeeze(total_power)
    bp["FreqRes"] = res
    # bp['WindowSec'] = 1 / res
    bp["Relative"] = relative
    bp["Chan"] = ch_names
    bp = bp.set_index("Chan").reset_index()
    # Add hidden attributes
    bp.bands_ = str(bands)
    return bp



def bandpower(
    data,
    sf=None,
    ch_names=None,
    hypno=None,
    include=(2, 3),
    win_sec=4,
    relative=True,
    bandpass=False,
    bands=[
        (0.5, 4, "Delta"),
        (4, 8, "Theta"),
        (8, 12, "Alpha"),
        (12, 16, "Sigma"),
        (16, 30, "Beta"),
        (30, 40, "Gamma"),
    ],
    kwargs_welch=dict(average="median", window="hamming"),
):
    
    """
    Calculate the Welch bandpower for each channel and, if specified, for each sleep stage.

    .. versionadded:: 0.1.6

    Parameters
    ----------
    data : np.array_like or :py:class:`mne.io.BaseRaw`
        1D or 2D EEG data. Can also be a :py:class:`mne.io.BaseRaw`, in which case ``data``,
        ``sf``, and ``ch_names`` will be automatically extracted, and ``data`` will also be
        converted from Volts (MNE default) to micro-Volts (YASA).
    sf : float
        The sampling frequency of data AND the hypnogram. Can be omitted if ``data`` is a
        :py:class:`mne.io.BaseRaw`.
    ch_names : list
        List of channel names, e.g. ['Cz', 'F3', 'F4', ...]. If None, channels will be labelled
        ['CHAN000', 'CHAN001', ...]. Can be omitted if ``data`` is a :py:class:`mne.io.BaseRaw`.
    hypno : array_like
        Sleep stage (hypnogram). If the hypnogram is loaded, the bandpower will be extracted for
        each sleep stage defined in ``include``.

        The hypnogram must have the exact same number of samples as ``data``. To upsample your
        hypnogram, please refer to :py:func:`yasa.hypno_upsample_to_data`.

        .. note::
            The default hypnogram format in YASA is a 1D integer vector where:

            - -2 = Unscored
            - -1 = Artefact / Movement
            - 0 = Wake
            - 1 = N1 sleep
            - 2 = N2 sleep
            - 3 = N3 sleep
            - 4 = REM sleep
    include : tuple, list or int
        Values in ``hypno`` that will be included in the mask. The default is (2, 3), meaning that
        the bandpower are sequentially calculated for N2 and N3 sleep. This has no effect when
        ``hypno`` is None.
    win_sec : int or float
        The length of the sliding window, in seconds, used for the Welch PSD calculation.
        Ideally, this should be at least two times the inverse of the lower frequency of
        interest (e.g. for a lower frequency of interest of 0.5 Hz, the window length should
        be at least 2 * 1 / 0.5 = 4 seconds).
    relative : boolean
        If True, bandpower is divided by the total power between the min and max frequencies
        defined in ``band``.
    bandpass : boolean
        If True, apply a standard FIR bandpass filter using the minimum and maximum frequencies
        in ``bands``. Fore more details, refer to :py:func:`mne.filter.filter_data`.
    bands : list of tuples
        List of frequency bands of interests. Each tuple must contain the lower and upper
        frequencies, as well as the band name (e.g. (0.5, 4, 'Delta')).
    kwargs_welch : dict
        Optional keywords arguments that are passed to the :py:func:`scipy.signal.welch` function.

    Returns
    -------
    bandpowers : :py:class:`pandas.DataFrame`
        Bandpower dataframe, in which each row is a channel and each column a spectral band.

    Notes
    -----
    For an example of how to use this function, please refer to
    https://github.com/raphaelvallat/yasa/blob/master/notebooks/08_bandpower.ipynb
    """
    
    from scipy import signal
    
    # Type checks
    assert isinstance(bands, list), "bands must be a list of tuple(s)"
    assert isinstance(relative, bool), "relative must be a boolean"
    assert isinstance(bandpass, bool), "bandpass must be a boolean"

    # Check if input data is a MNE Raw object
    if isinstance(data, mne.io.BaseRaw):
        sf = data.info["sfreq"]  # Extract sampling frequency
        ch_names = data.ch_names  # Extract channel names
        data = data.get_data(units=dict(eeg="uV", emg="uV", eog="uV", ecg="uV"))
        _, npts = data.shape
    else:
        # Safety checks
        assert isinstance(data, np.ndarray), "Data must be a numpy array."
        data = np.atleast_2d(data)
        assert data.ndim == 2, "Data must be of shape (nchan, n_samples)."
        nchan, npts = data.shape
        # assert nchan < npts, 'Data must be of shape (nchan, n_samples).'
        assert sf is not None, "sf must be specified if passing a numpy array."
        assert isinstance(sf, (int, float))
        if ch_names is None:
            ch_names = ["CHAN" + str(i).zfill(3) for i in range(nchan)]
        else:
            ch_names = np.atleast_1d(np.asarray(ch_names, dtype=str))
            assert ch_names.ndim == 1, "ch_names must be 1D."
            assert len(ch_names) == nchan, "ch_names must match data.shape[0]."

    if bandpass:
        # Apply FIR bandpass filter
        all_freqs = np.hstack([[b[0], b[1]] for b in bands])
        fmin, fmax = min(all_freqs), max(all_freqs)
        data = mne.filter.filter_data(data.astype("float64"), sf, fmin, fmax, verbose=0)

    win = int(win_sec * sf)  # nperseg

    if hypno is None:
        # Calculate the PSD over the whole data
        freqs, psd = signal.welch(data, sf, nperseg=win, **kwargs_welch)
        return bandpower_from_psd(psd, freqs, ch_names, bands=bands, relative=relative).set_index(
            "Chan"
        )
    else:
        # Per each sleep stage defined in ``include``.
        hypno = np.asarray(hypno)
        assert include is not None, "include cannot be None if hypno is given"
        include = np.atleast_1d(np.asarray(include))
        assert hypno.ndim == 1, "Hypno must be a 1D array."
        assert hypno.size == npts, "Hypno must have same size as data.shape[1]"
        assert include.size >= 1, "`include` must have at least one element."
        assert hypno.dtype.kind == include.dtype.kind, "hypno and include must have same dtype"
        assert np.in1d(
            hypno, include
        ).any(), "None of the stages specified in `include` are present in hypno."
        # Initialize empty dataframe and loop over stages
        df_bp = pd.DataFrame([])
        for stage in include:
            if stage not in hypno:
                continue
            data_stage = data[:, hypno == stage]
            freqs, psd = signal.welch(data_stage, sf, nperseg=win, **kwargs_welch)
            bp_stage = bandpower_from_psd(psd, freqs, ch_names, bands=bands, relative=relative)
            bp_stage["Stage"] = stage
            df_bp = pd.concat([df_bp, bp_stage], axis=0)
        return df_bp.set_index(["Stage", "Chan"])

def sliding_window(data, sf, window, step=None, axis=-1):
    """Calculate a sliding window of a 1D or 2D EEG signal."""
    from numpy.lib.stride_tricks import as_strided

    assert axis <= data.ndim, "Axis value out of range."
    assert isinstance(sf, (int, float)), "sf must be int or float"
    assert isinstance(window, (int, float)), "window must be int or float"
    assert isinstance(step, (int, float, type(None))), "step must be int, float or None."
    if isinstance(sf, float):
        assert sf.is_integer(), "sf must be a whole number."
        sf = int(sf)
    assert isinstance(axis, int), "axis must be int."

    # window and step in samples instead of points
    window *= sf
    step = window if step is None else step * sf

    if isinstance(window, float):
        assert window.is_integer(), "window * sf must be a whole number."
        window = int(window)

    if isinstance(step, float):
        assert step.is_integer(), "step * sf must be a whole number."
        step = int(step)

    assert step >= 1, "Stepsize may not be zero or negative."
    assert window < data.shape[axis], "Sliding window size may not exceed size of selected axis"

    # Define output shape
    shape = list(data.shape)
    shape[axis] = np.floor(data.shape[axis] / step - window / step + 1).astype(int)
    shape.append(window)

    # Calculate strides and time vector
    strides = list(data.strides)
    strides[axis] *= step
    strides.append(data.strides[axis])
    strided = as_strided(data, shape=shape, strides=strides)
    t = np.arange(strided.shape[-2]) * (step / sf)

    # Swap axis: n_epochs, ..., n_samples
    if strided.ndim > 2:
        strided = np.rollaxis(strided, -2, 0)
    return t, strided

def bandpower_from_psd_ndarray(psd, freqs, bands=[(0.5, 4, "Delta"), (4, 8, "Theta"), (8, 12, "Alpha"), (12, 16, "Sigma"), (16, 30, "Beta"), (30, 40, "Gamma")], relative=True):
    """Compute bandpowers in N-dimensional PSD."""
    # Type checks
    assert isinstance(bands, list), "bands must be a list of tuple(s)"
    assert isinstance(relative, bool), "relative must be a boolean"

    # Safety checks
    freqs = np.asarray(freqs)
    psd = np.asarray(psd)
    assert freqs.ndim == 1, "freqs must be a 1-D array of shape (n_freqs,)"
    assert psd.shape[-1] == freqs.shape[-1], "n_freqs must be last axis of psd"

    # Extract frequencies of interest
    all_freqs = np.hstack([[b[0], b[1]] for b in bands])
    fmin, fmax = min(all_freqs), max(all_freqs)
    idx_good_freq = np.logical_and(freqs >= fmin, freqs <= fmax)
    freqs = freqs[idx_good_freq]
    res = freqs[1] - freqs[0]

    # Trim PSD to frequencies of interest
    psd = psd[..., idx_good_freq]

    # Check if there are negative values in PSD
    if (psd < 0).any():
        msg = (
            "There are negative values in PSD. This will result in incorrect "
            "bandpower values. We highly recommend working with an "
            "all-positive PSD. For more details, please refer to: "
            "https://github.com/raphaelvallat/yasa/issues/29"
        )
        logger.warning(msg)

    # Calculate total power
    total_power = simpson(psd, dx=res, axis=-1)
    total_power = total_power[np.newaxis, ...]

    # Initialize empty array
    bp = np.zeros((len(bands), *psd.shape[:-1]), dtype=np.float64)

    # Enumerate over the frequency bands
    labels = []
    for i, band in enumerate(bands):
        b0, b1, la = band
        labels.append(la)
        idx_band = np.logical_and(freqs >= b0, freqs <= b1)
        bp[i] = simpson(psd[..., idx_band], dx=res, axis=-1)

    if relative:
        bp /= total_power
    return bp


class SleepStaging:
    """
    Automatic sleep staging of polysomnography data.

    The automatic sleep staging requires the
    `LightGBM <https://lightgbm.readthedocs.io/>`_ and
    `antropy <https://github.com/raphaelvallat/antropy>`_ packages.

    .. versionadded:: 0.4.0

    Parameters
    ----------
    raw : :py:class:`mne.io.BaseRaw`
        An MNE Raw instance.
    eeg_name : str
        The name of the EEG channel in ``raw``. Preferentially a central
        electrode referenced either to the mastoids (C4-M1, C3-M2) or to the
        Fpz electrode (C4-Fpz). Data are assumed to be in Volts (MNE default)
        and will be converted to uV.
    eog_name : str or None
        The name of the EOG channel in ``raw``. Preferentially,
        the left LOC channel referenced either to the mastoid (e.g. E1-M2)
        or Fpz. Can also be None.
    emg_name : str or None
        The name of the EMG channel in ``raw``. Preferentially a chin
        electrode. Can also be None.
    metadata : dict or None
        A dictionary of metadata (optional). Currently supported keys are:

        * ``'age'``: age of the participant, in years.
        * ``'male'``: sex of the participant (1 or True = male, 0 or
          False = female)

    Notes
    -----

    If you use the SleepStaging module in a publication, please cite the following publication:

    * Vallat, R., & Walker, M. P. (2021). An open-source, high-performance tool for automated
      sleep staging. Elife, 10. doi: https://doi.org/10.7554/eLife.70092

    We provide below some key points on the algorithm and its validation. For more details,
    we refer the reader to the peer-reviewed publication. If you have any questions,
    make sure to first check the
    `FAQ section <https://raphaelvallat.com/yasa/build/html/faq.html>`_ of the documentation.
    If you did not find the answer to your question, please feel free to open an issue on GitHub.

    **1. Features extraction**

    For each 30-seconds epoch and each channel, the following features are calculated:

    * Standard deviation
    * Interquartile range
    * Skewness and kurtosis
    * Number of zero crossings
    * Hjorth mobility and complexity
    * Absolute total power in the 0.4-30 Hz band.
    * Relative power in the main frequency bands (for EEG and EOG only)
    * Power ratios (e.g. delta / beta)
    * Permutation entropy
    * Higuchi and Petrosian fractal dimension

    In addition, the algorithm also calculates a smoothed and normalized version of these features.
    Specifically, a 7.5 min centered triangular-weighted rolling average and a 2 min past rolling
    average are applied. The resulting smoothed features are then normalized using a robust
    z-score.

    .. important:: The PSG data should be in micro-Volts. Do NOT transform (e.g. z-score) or filter
        the signal before running the sleep staging algorithm.

    The data are automatically downsampled to 100 Hz for faster computation.

    **2. Sleep stages prediction**

    YASA comes with a default set of pre-trained classifiers, which were trained and validated
    on ~3000 nights from the `National Sleep Research Resource <https://sleepdata.org/>`_.
    These nights involved participants from a wide age range, of different ethnicities, gender,
    and health status. The default classifiers should therefore works reasonably well on most data.

    The code that was used to train the classifiers can be found on GitHub at:
    https://github.com/raphaelvallat/yasa_classifier

    In addition with the predicted sleep stages, YASA can also return the predicted probabilities
    of each sleep stage at each epoch. This can be used to derive a confidence score at each epoch.

    .. important:: The predictions should ALWAYS be double-check by a trained
        visual scorer, especially for epochs with low confidence. A full
        inspection should be performed in the following cases:

        * Nap data, because the classifiers were exclusively trained on full-night recordings.
        * Participants with sleep disorders.
        * Sub-optimal PSG system and/or referencing

    .. warning:: N1 sleep is the sleep stage with the lowest detection accuracy. This is expected
        because N1 is also the stage with the lowest human inter-rater agreement. Be very
        careful for potential misclassification of N1 sleep (e.g. scored as Wake or N2) when
        inspecting the predicted sleep stages.

    References
    ----------
    If you use YASA's default classifiers, these are the main references for
    the `National Sleep Research Resource <https://sleepdata.org/>`_:

    * Dean, Dennis A., et al. "Scaling up scientific discovery in sleep
      medicine: the National Sleep Research Resource." Sleep 39.5 (2016):
      1151-1164.

    * Zhang, Guo-Qiang, et al. "The National Sleep Research Resource: towards
      a sleep data commons." Journal of the American Medical Informatics
      Association 25.10 (2018): 1351-1358.

    Examples
    --------
    For a concrete example, please refer to the example Jupyter notebook:
    https://github.com/raphaelvallat/yasa/blob/master/notebooks/14_automatic_sleep_staging.ipynb

    >>> import mne
    >>> import yasa
    >>> # Load an EDF file using MNE
    >>> raw = mne.io.read_raw_edf("myfile.edf", preload=True)
    >>> # Initialize the sleep staging instance
    >>> sls = yasa.SleepStaging(raw, eeg_name="C4-M1", eog_name="LOC-M2",
    ...                         emg_name="EMG1-EMG2",
    ...                         metadata=dict(age=29, male=True))
    >>> # Get the predicted sleep stages
    >>> hypno = sls.predict()
    >>> # Get the predicted probabilities
    >>> proba = sls.predict_proba()
    >>> # Get the confidence
    >>> confidence = proba.max(axis=1)
    >>> # Plot the predicted probabilities
    >>> sls.plot_predict_proba()

    The sleep scores can then be manually edited in an external graphical user interface
    (e.g. EDFBrowser), as described in the
    `FAQ <https://raphaelvallat.com/yasa/build/html/faq.html>`_.
    """

    def __init__(self, raw, eeg_name, *, eog_name=None, emg_name=None, metadata=None):
        # Type check
        assert isinstance(eeg_name, str)
        assert isinstance(eog_name, (str, type(None)))
        assert isinstance(emg_name, (str, type(None)))
        assert isinstance(metadata, (dict, type(None)))

        # Validate metadata
        if isinstance(metadata, dict):
            if "age" in metadata.keys():
                assert 0 < metadata["age"] < 120, "age must be between 0 and 120."
            if "male" in metadata.keys():
                metadata["male"] = int(metadata["male"])
                assert metadata["male"] in [0, 1], "male must be 0 or 1."

        # Validate Raw instance and load data
        assert isinstance(raw, mne.io.BaseRaw), "raw must be a MNE Raw object."
        sf = raw.info["sfreq"]
        ch_names = np.array([eeg_name, eog_name, emg_name])
        ch_types = np.array(["eeg", "eog", "emg"])
        keep_chan = []
        for c in ch_names:
            if c is not None:
                assert c in raw.ch_names, "%s does not exist" % c
                keep_chan.append(True)
            else:
                keep_chan.append(False)
        # Subset
        ch_names = ch_names[keep_chan].tolist()
        ch_types = ch_types[keep_chan].tolist()
        # Keep only selected channels (creating a copy of Raw)
        raw_pick = raw.copy().pick(ch_names)

        # Downsample if sf != 100
        assert sf > 80, "Sampling frequency must be at least 80 Hz."
        if sf != 100:
            raw_pick.resample(100, npad="auto")
            sf = raw_pick.info["sfreq"]

        # Get data and convert to microVolts
        data = raw_pick.get_data(units=dict(eeg="uV", emg="uV", eog="uV", ecg="uV"))

        # Extract duration of recording in minutes
        duration_minutes = data.shape[1] / sf / 60
        if duration_minutes < 5:
            msg = (
                "Insufficient data. A minimum of 5 minutes of data is recommended "
                "otherwise results may be unreliable."
            )
            logger.warning(msg)

        # Add to self
        self.sf = sf
        self.ch_names = ch_names
        self.ch_types = ch_types
        self.data = data
        self.metadata = metadata

    def fit(self):
        """Extract features from data.

        Returns
        -------
        self : returns an instance of self.
        """
        #######################################################################
        # MAIN PARAMETERS
        #######################################################################

        # Bandpass filter
        freq_broad = (0.4, 30)
        # FFT & bandpower parameters
        win_sec = 5  # = 2 / freq_broad[0]
        sf = self.sf
        win = int(win_sec * sf)
        kwargs_welch = dict(window="hamming", nperseg=win, average="median")
        bands = [
            (0.4, 1, "sdelta"),
            (1, 4, "fdelta"),
            (4, 8, "theta"),
            (8, 12, "alpha"),
            (12, 16, "sigma"),
            (16, 30, "beta"),
        ]

        #######################################################################
        # CALCULATE FEATURES
        #######################################################################

        features = []

        for i, c in enumerate(self.ch_types):
            # Preprocessing
            # - Filter the data
            dt_filt = filter_data(
                self.data[i, :], sf, l_freq=freq_broad[0], h_freq=freq_broad[1], verbose=False
            )
            # - Extract epochs. Data is now of shape (n_epochs, n_samples).
            times, epochs = sliding_window(dt_filt, sf=sf, window=30)

            # Calculate standard descriptive statistics
            hmob, hcomp = ant.hjorth_params(epochs, axis=1)

            feat = {
                "std": np.std(epochs, ddof=1, axis=1),
                "iqr": sp_stats.iqr(epochs, rng=(25, 75), axis=1),
                "skew": sp_stats.skew(epochs, axis=1),
                "kurt": sp_stats.kurtosis(epochs, axis=1),
                "nzc": ant.num_zerocross(epochs, axis=1),
                "hmob": hmob,
                "hcomp": hcomp,
            }

            # Calculate spectral power features (for EEG + EOG)
            freqs, psd = sp_sig.welch(epochs, sf, **kwargs_welch)
            if c != "emg":
                bp = bandpower_from_psd_ndarray(psd, freqs, bands=bands)
                for j, (_, _, b) in enumerate(bands):
                    feat[b] = bp[j]

            # Add power ratios for EEG
            if c == "eeg":
                delta = feat["sdelta"] + feat["fdelta"]
                feat["dt"] = delta / feat["theta"]
                feat["ds"] = delta / feat["sigma"]
                feat["db"] = delta / feat["beta"]
                feat["at"] = feat["alpha"] / feat["theta"]

            # Add total power
            idx_broad = np.logical_and(freqs >= freq_broad[0], freqs <= freq_broad[1])
            dx = freqs[1] - freqs[0]
            feat["abspow"] = np.trapz(psd[:, idx_broad], dx=dx)

            # Calculate entropy and fractal dimension features
            feat["perm"] = np.apply_along_axis(ant.perm_entropy, axis=1, arr=epochs, normalize=True)
            feat["higuchi"] = np.apply_along_axis(ant.higuchi_fd, axis=1, arr=epochs)
            feat["petrosian"] = ant.petrosian_fd(epochs, axis=1)

            # Convert to dataframe
            feat = pd.DataFrame(feat).add_prefix(c + "_")
            features.append(feat)

        #######################################################################
        # SMOOTHING & NORMALIZATION
        #######################################################################

        # Save features to dataframe
        features = pd.concat(features, axis=1)
        features.index.name = "epoch"

        # Apply centered rolling average (15 epochs = 7 min 30)
        # Triang: [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.,
        #          0.875, 0.75, 0.625, 0.5, 0.375, 0.25, 0.125]
        rollc = features.rolling(window=15, center=True, min_periods=1, win_type="triang").mean()
        rollc[rollc.columns] = robust_scale(rollc, quantile_range=(5, 95))
        rollc = rollc.add_suffix("_c7min_norm")

        # Now look at the past 2 minutes
        rollp = features.rolling(window=4, min_periods=1).mean()
        rollp[rollp.columns] = robust_scale(rollp, quantile_range=(5, 95))
        rollp = rollp.add_suffix("_p2min_norm")

        # Add to current set of features
        features = features.join(rollc).join(rollp)

        #######################################################################
        # TEMPORAL + METADATA FEATURES AND EXPORT
        #######################################################################

        # Add temporal features
        features["time_hour"] = times / 3600
        features["time_norm"] = times / times[-1]

        # Add metadata if present
        if self.metadata is not None:
            for c in self.metadata.keys():
                features[c] = self.metadata[c]

        # Downcast float64 to float32 (to reduce size of training datasets)
        cols_float = features.select_dtypes(np.float64).columns.tolist()
        features[cols_float] = features[cols_float].astype(np.float32)
        # Make sure that age and sex are encoded as int
        if "age" in features.columns:
            features["age"] = features["age"].astype(int)
        if "male" in features.columns:
            features["male"] = features["male"].astype(int)

        # Sort the column names here (same behavior as lightGBM)
        features.sort_index(axis=1, inplace=True)

        # Add to self
        self._features = features
        self.feature_name_ = self._features.columns.tolist()

    def get_features(self):
        """Extract features from data and return a copy of the dataframe.

        Returns
        -------
        features : :py:class:`pandas.DataFrame`
            Feature dataframe.
        """
        if not hasattr(self, "_features"):
            self.fit()
        return self._features.copy()

    def _validate_predict(self, clf):
        """Validate classifier."""
        # Check that we're using exactly the same features
        # Note that clf.feature_name_ is only available in lightgbm>=3.0
        f_diff = np.setdiff1d(clf.feature_name_, self.feature_name_)
        if len(f_diff):
            raise ValueError(
                "The following features are present in the "
                "classifier but not in the current features set:",
                f_diff,
            )
        f_diff = np.setdiff1d(
            self.feature_name_,
            clf.feature_name_,
        )
        if len(f_diff):
            raise ValueError(
                "The following features are present in the "
                "current feature set but not in the classifier:",
                f_diff,
            )

    def _load_model(self, path_to_model):
        """Load the relevant trained classifier."""
        if path_to_model == "auto":
            from pathlib import Path

            clf_dir = os.path.join(str(Path(__file__).parent), "classifiers/")
            name = "clf_eeg"
            name = name + "+eog" if "eog" in self.ch_types else name
            name = name + "+emg" if "emg" in self.ch_types else name
            # e.g. clf_eeg+eog+emg+demo_lgb_0.4.0.joblib
            all_matching_files = glob.glob(clf_dir + name + "*.joblib")
            # Find the latest file
            path_to_model = np.sort(all_matching_files)[-1]
        # Check that file exists
        assert os.path.isfile(path_to_model), "File does not exist."
        logger.info("Using pre-trained classifier: %s" % path_to_model)
        # Load using Joblib
        clf = joblib.load(path_to_model)
        # Validate features
        self._validate_predict(clf)
        return clf

    def predict(self, path_to_model="auto"):
        """
        Return the predicted sleep stage for each 30-sec epoch of data.

        Currently, only classifiers that were trained using a
        `LGBMClassifier <https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html>`_
        are supported.

        Parameters
        ----------
        path_to_model : str or "auto"
            Full path to a trained LGBMClassifier, exported as a joblib file. Can be "auto" to
            use YASA's default classifier.

        Returns
        -------
        pred : :py:class:`numpy.ndarray`
            The predicted sleep stages.
        """
        if not hasattr(self, "_features"):
            self.fit()
        # Load and validate pre-trained classifier
        clf = self._load_model(path_to_model)
        # Now we make sure that the features are aligned
        X = self._features.copy()[clf.feature_name_]
        # Predict the sleep stages and probabilities
        self._predicted = clf.predict(X)
        proba = pd.DataFrame(clf.predict_proba(X), columns=clf.classes_)
        proba.index.name = "epoch"
        self._proba = proba
        return self._predicted.copy()

    def predict_proba(self, path_to_model="auto"):
        """
        Return the predicted probability for each sleep stage for each 30-sec epoch of data.

        Currently, only classifiers that were trained using a
        `LGBMClassifier <https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html>`_
        are supported.

        Parameters
        ----------
        path_to_model : str or "auto"
            Full path to a trained LGBMClassifier, exported as a joblib file. Can be "auto" to
            use YASA's default classifier.

        Returns
        -------
        proba : :py:class:`pandas.DataFrame`
            The predicted probability for each sleep stage for each 30-sec epoch of data.
        """
        if not hasattr(self, "_proba"):
            self.predict(path_to_model)
        return self._proba.copy()
