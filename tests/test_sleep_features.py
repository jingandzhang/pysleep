import sys, os
file_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, file_dir + '/../mednickdb_pysleep/')
from sleep_features import detect_spindles, detect_slow_oscillation, assign_stage_to_feature_events, sleep_feature_variables_per_stage, detect_rems
import time
import pytest
import pickle
import numpy as np
import pandas as pd
import yaml


def test_spindle_detection():
    # TODO make a real test case...
    start_time = time.time()
    edf = os.path.join(file_dir, 'testfiles/example1_sleep_rec.edf')
    study_settings = yaml.safe_load(open(os.path.join(file_dir, 'testfiles/example1_study_settings.yaml'), 'rb'))
    chans_to_consider = list(study_settings['known_eeg_chans'].keys())
    spindles = detect_spindles(edf_filepath=edf, algo='Ferrarelli2007', chans_to_consider=chans_to_consider)
    end_time = time.time()
    print('Spindles took', end_time-start_time)
    assert spindles is not None
    spindles.to_csv(os.path.join(file_dir, 'testfiles/example1_spindle_events.csv'), index=False)


def test_so_detection():
    # TODO make a real test case...
    start_time = time.time()
    edf = os.path.join(file_dir,'testfiles/example1_sleep_rec.edf')
    study_settings = yaml.safe_load(open(os.path.join(file_dir, 'testfiles/example1_study_settings.yaml'), 'rb'))
    chans_to_consider = list(study_settings['known_eeg_chans'].keys())
    slow_oscillations = detect_slow_oscillation(edf_filepath=edf, chans_to_consider=chans_to_consider)
    end_time = time.time()
    print('SO took', end_time - start_time)
    assert slow_oscillations is not None
    pytest.slow_oscillations = slow_oscillations


# def test_rem_detection():
#     edf = os.path.join(file_dir, 'testfiles/example2_sleep_rec.edf')
#     study_settings = yaml.safe_load(open(os.path.join(file_dir, 'testfiles/example1_study_settings.yaml'), 'rb'))
#     chans_to_consider = list(study_settings['known_eog_chans'].keys())
#     epochstages_file = file_dir + '/testfiles/example2_epoch_stages.pkl'
#     epoch_stages = pickle.load(open(epochstages_file, 'rb'))
#     rem_locs_df = detect_rems(edf, 'LOC', 'ROC', epoch_stages)
#     assert rem_locs_df is not None
#     assert rem_locs_df.shape[0] > 0


def test_density_and_mean_features_calculations():
    #TODO should check actual spindle averages (assuming deterministic spindle algo)
    epochstages_file = os.path.join(file_dir, 'testfiles/example1_epoch_stages.pkl')
    epoch_stages = pickle.load(open(epochstages_file, 'rb'))
    spindles = pd.read_csv(file_dir + '/testfiles/example1_spindle_events.csv')
    spindle_events = assign_stage_to_feature_events(spindles, epoch_stages)
    channels = spindle_events['chan'].unique()
    stages = ['n2', 'n3']
    features = sleep_feature_variables_per_stage(spindle_events, epoch_stages, stages_to_consider=stages)
    assert features.shape[0] == len(stages)
    expected_cols = ['av_density', 'av_count'] + ['av_' + col for col in spindle_events.columns]+list(spindle_events.columns)
    assert all([col in expected_cols for col in features.columns])
    features_per_chan = sleep_feature_variables_per_stage(spindle_events, epoch_stages, av_across_channels=False, stages_to_consider=stages)
    chan_stage_missing_spindles = 1
    assert features_per_chan.shape[0] == len(stages)*len(channels)-chan_stage_missing_spindles
    assert set(features_per_chan['chan'].unique()) == set(channels)
    assert set(features_per_chan['stage'].unique()) == set(stages)

    # test if density is 0 for channels that dont have spindles
    channels = np.append(channels, 'F9').tolist()
    features_per_chan = sleep_feature_variables_per_stage(spindle_events, epoch_stages, channels=channels,
                                                          av_across_channels=False, stages_to_consider=stages)
    assert set(features_per_chan['chan'].unique()) == set(channels)
    assert all(0 == features_per_chan.loc[features_per_chan['chan'] == 'F9', 'av_count'])

    os.remove(os.path.join(file_dir, 'testfiles/example1_spindle_events.csv'))
