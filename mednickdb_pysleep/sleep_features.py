from wonambi import Dataset
from wonambi.detect import DetectSpindle, DetectSlowWave
from typing import List, Tuple, Dict
from .pysleep_utils import *
from .pysleep_defaults import *
from .sleep_architecture import sleep_stage_architecture


def detect_spindles(edf_filepath: str,
                    algo: str='Lacourse2018',
                    chans_to_consider: List[str]=None,
                    start_time: float=None,
                    end_time: float=None)->pd.DataFrame:
    """
    Detect spindles locations in an edf file for each channel
    :param edf_filepath: path of edf file to load. Will maybe work with other filetypes. untested.
    :param algo: which algorithm to use to detect spindles. See wonambi methods: https://wonambi-python.github.io/gui/methods.html
    :param chans_to_consider: which channels to detect spindles on, must match edf channel names
    :param start_time: time of edf to begin detection
    :param end_time: time of edf to end detection
    :return: returns dataframe of spindle locations, with columns for chan, start, duration and other spindle properties, sorted by onset
    """
    d = Dataset(edf_filepath)
    data = d.read_data(begtime=start_time, endtime=end_time, chan=chans_to_consider)
    detection = DetectSpindle(algo)
    spindles_detected = detection(data)
    spindles_df = pd.DataFrame(spindles_detected.events)
    col_map = {'start': 'onset',
               'end': None,
               'peak_time': 'peak_time',
               'peak_val_det': 'peak_uV_in_spindle_band',
               'peak_val_orig': None,
               'dur': 'duration',
               'auc_det': None,
               'auc_orig': None,
               'rms_det': None,
               'rms_orig': None,
               'power_orig': None,
               'peak_freq': 'freq_peak',
               'ptp_det': None,
               'ptp_orig': None,
               'chan': 'chan'}
    cols_to_keep = set(spindles_df.columns) - set([k for k, v in col_map.items() if v is None])
    spindles_df = spindles_df.loc[:, cols_to_keep]
    spindles_df.columns = [col_map[k] for k in spindles_df.columns]
    spindles_df['peak_time'] = spindles_df['peak_time'] - spindles_df['onset']
    spindles_df['description'] = 'spindle'
    spindles_df['eventtype'] = 'sleep_feature'
    return spindles_df.sort_values('onset')


def detect_slow_oscillation(edf_filepath: str,
                            algo: str='AASM/Massimini2004',
                            chans_to_consider: List[str]=None,
                            start_time: float=None,
                            end_time: float=None)->pd.DataFrame:
    """
    Detect slow waves (slow oscillations) locations in an edf file for each channel
    :param edf_filepath: path of edf file to load. Will maybe work with other filetypes. untested.
    :param algo: which algorithm to use to detect spindles. See wonambi methods: https://wonambi-python.github.io/gui/methods.html
    :param chans_to_consider: which channels to detect spindles on, must match edf channel names
    :param start_time: time of edf to begin detection
    :param end_time: time of edf to end detection
    :return: returns dataframe of spindle locations, with columns for chan, start, duration and other spindle properties, sorted by onset
    """
    d = Dataset(edf_filepath)
    data = d.read_data(begtime=start_time, endtime=end_time, chan=chans_to_consider)
    detection = DetectSlowWave(algo)
    sos_detected = detection(data)
    sos_df = pd.DataFrame(sos_detected.events)
    col_map = {'start': 'onset',
               'end': None,
               'trough_time': 'trough_time',
               'zero_time':'zero_time',
               'peak_time':'peak_time',
               'trough_val': 'trough_val',
               'peak_val': 'peak_val',
               'dur': 'duration',
               'ptp': None,
               'chan': 'chan'}
    cols_to_keep = set(sos_df.columns) - set([k for k, v in col_map.items() if v is None])
    sos_df = sos_df.loc[:, cols_to_keep]
    sos_df.columns = [col_map[k] for k in sos_df.columns]
    sos_df['peak_time'] = sos_df['peak_time'] - sos_df['onset']
    sos_df['trough_time'] = sos_df['trough_time'] - sos_df['onset']
    sos_df['zero_time'] = sos_df['zero_time'] - sos_df['onset']
    sos_df['description'] = 'slow_oscillation'
    sos_df['eventtype'] = 'sleep_feature'
    return sos_df.sort_values('onset')


def assign_stage_to_feature_events(feature_events: pd.DataFrame, epochstages: list) -> pd.DataFrame:
    """
    :param feature_events: events dataframe, with start and duration columns
    :param epochstages: stages, where the first stage starts at 0 seconds on the events timeline
    :return: the modified events df, with a stage column
    """
    if isinstance(epochstages, list):
        stage_events = convert_epochstages_to_eegevents(epochstages)
    elif isinstance(epochstages, pd.DataFrame):
        stage_events = epochstages
    else:
        raise ValueError('epochstages is of unknown type. Should be dict or dataframe.')

    def check_overlap(start, duration, stage_events):
        end = start + duration
        for idx, stage in stage_events.iterrows():
            if overlap(start, end, stage['onset'], stage['onset']+stage['duration']):
                return stage['description']
        return unknown_stage

    feature_events['stage'] = feature_events.apply(lambda x: check_overlap(x['onset'], x['duration'], stage_events), axis=1)
    return feature_events


def sleep_feature_variables_per_stage(feature_events: pd.DataFrame,
                                      epoch_stages: list,
                                      stages_to_consider: List[str]=stages_to_consider,
                                      channels: List[str]=None,
                                      av_across_channels: bool=True):
    """
    Calculate the density, and mean of other important sleep feature variables (amp, power, peak freq, etc)
    :param feature_events: dataframe of a single event type (spindle, slow osc, rem, etc)
    :param epoch_stages: epoch_stages list, the list of stages for each 30 second interval
    :param stages_to_consider: The stages to extract for, i.e. you probably want to leave out REM when doing spindles
    :param channels: if None consider all channels.
    :param av_across_channels: whether to average across channels, or return separate for each channel
    :return: dataframe of with len(stage)*len(chan) or len(stage) rows with density + mean of each feature as columns
    """
    assert len(feature_events['description'].unique()) == 1, 'Only a single event type should be included'
    mins_in_stage, _, _ = sleep_stage_architecture(epoch_stages, stages_to_consider=stages_to_consider)
    non_var_cols = ['stage', 'eventtype', 'onset', 'description', 'chan', 'stage']
    features_per_stage_cont = []
    for stage, feature_data_per_stage in feature_events.groupby('stage'):
        if stage in stages_to_consider:
            per_chan_cont = []
            for chan, feature_data_per_stage_chan in feature_data_per_stage.groupby('chan'):
                if channels is None or chan in channels:
                    features_per_chan = feature_data_per_stage_chan.drop(non_var_cols, axis=1).mean()
                    features_per_chan['density'] = feature_data_per_stage_chan.shape[0]/mins_in_stage[stage]
                    features_per_chan['count'] = feature_data_per_stage_chan.shape[0]
                    features_per_chan.index = ['av_'+col for col in features_per_chan.index]
                    features_per_chan['chan'] = chan
                    per_chan_cont.append(features_per_chan)
            if len(per_chan_cont) > 0:
                features_per_stage = pd.concat(per_chan_cont, axis=1).T
                if av_across_channels:
                    features_per_stage = features_per_stage.drop('chan', axis=1).mean()
                features_per_stage['stage'] = stage
                features_per_stage_cont.append(features_per_stage)
    if len(features_per_stage_cont) > 0:
        if av_across_channels:
            features_df = pd.concat(features_per_stage_cont, axis=1).T
        else:
            features_df = pd.concat(features_per_stage_cont, axis=0)
        features_df['description'] = feature_events['description'][0]
        features_df['eventtype'] = feature_events['eventtype'][0]
        return features_df
    else:
        print('No events in given stages')
        return None