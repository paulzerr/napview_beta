import os
import ast
import time
import json
import numpy as np
import mne


# try:
#     from database_handler import DatabaseHandler
#     from helpers import configure_logger, ConfigManager
# except:
from .database_handler import DatabaseHandler
from .helpers import configure_logger, ConfigManager

class Analyzer:

    def __init__(self, base_path, mode):

        self.logger = configure_logger(base_path)
        self.logger.info('Analyzer: started...')

        self.mode             = mode
        self.base_path        = base_path
        self.results_path     = os.path.join(base_path, "data", "results")
        self.eeg_data         = None
        self.info             = None
        self.analysis_results = []

        self.config_manager = ConfigManager(base_path)
        self.config = self.config_manager.load_config(instance=self)

        self.db_handler = DatabaseHandler(self.base_path)
        self.db_handler.setup_database(self.db_file_path, create_tables=False)

        if self.mode == 'U-Sleep':
            from usleep_api import USleepAPI
            try:
                self.api = USleepAPI(api_token=self.api_token)
                self.logger.info('Analyzer: Scorer: Usleep API connected, token valid')
                self.api.delete_all_sessions()
            except Exception as e:
                self.logger.error(f'Analyzer: Failed to connect to Usleep API: {e}', exc_info=True)
                self.api = None

    def make_mne_object(self, data, sample_rate):
        try:
            self.info = mne.create_info(
                ch_names=json.loads(self.eeginfo.channel_names),
                sfreq=sample_rate,
                ch_types='eeg'
            )
            self.raw = mne.io.RawArray(data, self.info)
            self.sf = sample_rate
        except Exception as e:
            self.logger.error(f'Analyzer: Failed to create MNE object: {e}', exc_info=True)
            self.raw = None


    def volts_to_microvolts(self,data):
        return data * 1e6

    def calculate_noise_level(self,channel_data):
        if np.all(channel_data == 0):
            return float('inf')  
        return np.std(channel_data)

    def find_lowest_noise_channel(self, channel_names):
        if not channel_names:
            return None  # Return None if the channel list is empty

        lowest_noise = float('inf')
        best_channel = None
        for channel_name in channel_names:
            try:
                channel_data = self.raw.copy().pick([channel_name]).get_data()
                noise_level = self.calculate_noise_level(channel_data)
                if noise_level < lowest_noise:
                    lowest_noise = noise_level
                    best_channel = channel_name
            except Exception as e:
                self.logger.warning(f'Analyzer: Failed to calculate noise level for channel {channel_name}: {e}', exc_info=True)
        return best_channel


    def analyze_epoch_usleep_scorer(self, start_time):
        small_edf_filepath = os.path.join(self.base_path, "data", "edfs", "temp_edf.edf")
        classifier_results_filepath = os.path.join(self.base_path, "data", "edfs", "temp_results.npy")
        try:
            mne.export.export_raw(small_edf_filepath, self.raw, fmt='edf', overwrite=True)
            self.logger.info(f'Analyzer: Scorer: Temporary EDF created for scoring: {small_edf_filepath}')
        except Exception as e:
            self.logger.error(f'Analyzer: Scorer: Failed to create temporary EDF: {e}', exc_info=True)
            return None
        try:
            if self.api is not None:
                hypnogram, log = self.api.quick_predict(
                    input_file_path=small_edf_filepath,
                    output_file_path=classifier_results_filepath,
                    anonymize_before_upload=False,
                    with_confidence_scores=True,
                    model="U-Sleep v2.0",
                    data_per_prediction=128 * 30,
                )
                self.logger.info('Analyzer: Scorer: Usleep epoch scoring complete')
                results = np.load(classifier_results_filepath) / 12
            else:
                self.logger.error('Analyzer: Scorer: Usleep API not initialized', exc_info=True)
                results = np.zeros((1, 5))
        except Exception as e:
            self.logger.error(f'Analyzer: Scorer: Failed to get prediction: {e}', exc_info=True)
            results = np.zeros((1, 5))

        analysis_result = {
            'start_time': start_time,
            'w': float(results[0][0]),
            'n1': float(results[0][1]),
            'n2': float(results[0][3]),
            'n3': float(results[0][2]),
            'rem': float(results[0][4]),
        }

        results_output_filepath = os.path.join(self.base_path, "data", "results", "staging_results.txt")
        try:
            with open(results_output_filepath, 'a') as f:
                json.dump(analysis_result, f)
                f.write('\n')
            #self.logger.info('Analyzer: U-Sleep scorer: predictions saved to file')
        except Exception as e:
            self.logger.error(f'Analyzer: Failed to save predictions to file: {e}', exc_info=True)
        return analysis_result



    def analyze_epoch_yasa(self, start_time):

        try:
            from yasa_staging_minimal import bandpower
        except:
            from .yasa_staging_minimal import bandpower

        def find_channel(channels, options):
            for option in options:
                for ch in channels:
                    if option in ch.lower():
                        return ch
            return None

        try:
            preferred_yasa_channel = self.config.get('preferred_yasa_channel')
            if preferred_yasa_channel and preferred_yasa_channel in self.raw.ch_names:
                bandpower_channel_name = preferred_yasa_channel
            else:
                bandpower_channel_name = find_channel(self.raw.ch_names, ["c3", "c4", "o1", "o2"])
                if not bandpower_channel_name:
                    bandpower_channel_name = self.raw.ch_names[0]

            # spindle_channel_name = find_channel(self.raw.ch_names, ["c3", "c4"])
            # if not spindle_channel_name:
            #     spindle_channel_name = self.raw.ch_names[0]

            # eye_movement_channel_name = find_channel(self.raw.ch_names, ["eog"])
            # if not eye_movement_channel_name:
            #     eye_movement_channel_name = find_channel(self.raw.ch_names, ["fp1", "fp2"])
            # if not eye_movement_channel_name:
            #     eye_movement_channel_name = self.raw.ch_names[0]

            if bandpower_channel_name in ["c3", "c4"]:
                try:
                    c3_noise = self.calculate_noise_level(self.raw.copy().pick(["c3"]).get_data())
                    c4_noise = self.calculate_noise_level(self.raw.copy().pick(["c4"]).get_data())
                    bandpower_channel_name = "c3" if c3_noise < c4_noise else "c4"
                except Exception as e:
                    self.logger.warning(f'Analyzer: YASA: Failed to calculate noise level for bandpower channels: {e}', exc_info=True)
                    bandpower_channel_name = self.raw.ch_names[0]

            # if spindle_channel_name in ["c3", "c4"]:
            #     try:
            #         c3_noise = self.calculate_noise_level(self.raw.copy().pick(["c3"]).get_data())
            #         c4_noise = self.calculate_noise_level(self.raw.copy().pick(["c4"]).get_data())
            #         spindle_channel_name = "c3" if c3_noise < c4_noise else "c4"
            #     except Exception as e:
            #         self.logger.warning(f'Analyzer: YASA: Failed to calculate noise level for spindle channels: {e}', exc_info=True)
            #         spindle_channel_name = self.raw.ch_names[0]

            bandpower_channel = self.raw.copy().pick([bandpower_channel_name]).apply_function(self.volts_to_microvolts)
            #spindle_channel = self.raw.copy().pick([spindle_channel_name]).apply_function(self.volts_to_microvolts)
            #eye_movement_channel = self.raw.copy().pick([eye_movement_channel_name]).apply_function(self.volts_to_microvolts)

            analysis_result = {
                'start_time': start_time,
                'eye_movements': 0,
                'spindles': 0,
                'alpha_power': 0,
                'beta_power': 0,
                'theta_power': 0,
                'delta_power': 0,
                'gamma_power': 0,
            }

            try:
                bands = [(0.5, 4, 'Delta'), (4, 8, 'Theta'), (8, 12, 'Alpha'),
                         (12, 16, 'Sigma'), (16, 30, 'Beta'), (30, 40, 'Gamma')]
                bandpower_df = bandpower(bandpower_channel, bands=bands)
                analysis_result.update({
                    'alpha_power': bandpower_df['Alpha'].mean(),
                    'beta_power': bandpower_df['Beta'].mean(),
                    'theta_power': bandpower_df['Theta'].mean(),
                    'delta_power': bandpower_df['Delta'].mean(),
                    'gamma_power': bandpower_df['Gamma'].mean(),
                })
            except Exception as e:
                self.logger.warning(f'Analyzer: YASA: Failed to compute band power: {e}', exc_info=True)

            # try:
            #     spindles = self.yasa.spindles_detect(spindle_channel)
            #     analysis_result['spindles'] = len(spindles) if spindles is not None else 0
            # except Exception as e:
            #     self.logger.warning(f'Analyzer: YASA: Failed to detect spindles: {e}', exc_info=True)


            # TODO: fix eye movement detection
            # try:
            #     eye_movements = self.yasa.rem_detect(eye_movement_channel,eye_movement_channel,self.sf)
            #     analysis_result['eye_movements'] = len(eye_movements)
            # except Exception as e:
            #     self.logger.warning(f'Analyzer: YASA: Failed to detect eye movements: {e}', exc_info=True)

            results_output_filepath = os.path.join(self.base_path, "data", "results", "yasa_results.txt")

            try:
                with open(results_output_filepath, 'a') as f:
                    json.dump(analysis_result, f)
                    f.write('\n')
                #self.logger.info(f'Analyzer: YASA: Analysis result saved to file: {results_output_filepath}')
            except Exception as e:
                self.logger.info(f'Analyzer: YASA: Failed to save analysis result to file: {e}', exc_info=True)
            return analysis_result
        except Exception as e:
            self.logger.error(f'Analyzer: YASA: Failed to analyze epoch: {e}', exc_info=True)
            return None

    def analyze_epoch_yasa_scorer(self, start_time):

        try:
            from yasa_staging_minimal import SleepStaging
        except:
            from .yasa_staging_minimal import SleepStaging

        def find_channels_by_keywords(channels, primary_keywords, fallback_keywords=None, max_channels=2):
            selected_channels = []
            for ch in channels:
                if any(keyword in ch.lower() for keyword in primary_keywords):
                    selected_channels.append(ch)
                    if len(selected_channels) == max_channels:
                        return selected_channels
            if fallback_keywords:
                for ch in channels:
                    if any(keyword in ch.lower() for keyword in fallback_keywords):
                        selected_channels.append(ch)
                        if len(selected_channels) == max_channels:
                            return selected_channels
            return selected_channels

        analysis_result = {
            'start_time': start_time,
            'n1': 0,
            'n2': 0,
            'n3': 0,
            'rem': 0,
            'w': 0,
        }

        try:
            eeg_keywords = ["c3", "c4", "o1", "o2", "oz", "fp1", "fp2", "f3", "f4", "t3", "t4", "p3", "p4", "cz", "fz", "pz"]
            eog_primary_keywords = ["eog"]
            eog_fallback_keywords = ["fp1", "fp2", "fpz"]
            emg_keywords = ["emg", "chin"]

            preferred_yasa_channel = self.config.get('preferred_yasa_channel')
            if preferred_yasa_channel and preferred_yasa_channel in self.raw.ch_names:
                eeg_channel = preferred_yasa_channel
            else:
                eeg_keywords = ["c3", "c4", "o1", "o2", "oz", "fp1", "fp2", "f3", "f4", "t3", "t4", "p3", "p4", "cz", "fz", "pz"]
                eeg_channel = find_channels_by_keywords(self.raw.ch_names, eeg_keywords)
                if not eeg_channel:
                    eeg_channel = self.raw.ch_names[0]
                else:
                    eeg_channel = self.find_lowest_noise_channel(eeg_channel)

            # eeg_channel = find_channels_by_keywords(self.raw.ch_names, eeg_keywords)
            # if not eeg_channel:
            #     eeg_channel = self.raw.ch_names[0]
            # else:
            #     eeg_channel = self.find_lowest_noise_channel(eeg_channel)

            eog_channel = find_channels_by_keywords(self.raw.ch_names, eog_primary_keywords, eog_fallback_keywords)
            if eog_channel:
                eog_channel = self.find_lowest_noise_channel(eog_channel)

            emg_channel = find_channels_by_keywords(self.raw.ch_names, emg_keywords)
            if emg_channel:
                emg_channel = self.find_lowest_noise_channel(emg_channel)

            raw_microvolts = self.raw.copy().apply_function(self.volts_to_microvolts)

            self.logger.info(f'Analyzer: YASA will now analyse recent eeg data, using channels: EEG: {eeg_channel}, EOG: {eog_channel}, EMG: {emg_channel}')

            sls = SleepStaging(raw_microvolts, eeg_name=eeg_channel, eog_name=eog_channel, emg_name=emg_channel)
            
            stage_probs = sls.predict_proba()
            latest_epoch_probs = stage_probs.iloc[-1]

            analysis_result.update({
                'n1': latest_epoch_probs['N1'],
                'n2': latest_epoch_probs['N2'],
                'n3': latest_epoch_probs['N3'],
                'rem': latest_epoch_probs['R'],
                'w': latest_epoch_probs['W'],
            })
        except Exception as e:
            self.logger.error(f'Analyzer: YASA Stager: Failed to perform sleep staging: {e}',exc_info=True)
            try:
                self.logger.error(f'Channels: {self.raw.ch_names}, eeg: {eeg_channel}, eog: {eog_channel}, emg: {emg_channel}')
            except Exception as e:
                self.logger.error(f'Analyzer: YASA Stager: unable to log channels during exception: {e}',exc_info=True)

        results_output_filepath = os.path.join(self.base_path, "data", "results", "staging_results.txt")
        try:
            with open(results_output_filepath, 'a') as f:
                json.dump(analysis_result, f)
                f.write('\n')
            #self.logger.info('Analyzer: YASA Stager: Analysis result saved to file')
        except Exception as e:
            self.logger.error(f'Analyzer: YASA Stager: Failed to save analysis result to file: {e}', exc_info=True)

        return analysis_result

    def shutdown(self):
        self.logger.info("Analyzer: Shutting down...")

    def maximize_analysis_epoch(self, start_idx, end_idx, single_epoch=False):
        try:
            total_samples = self.db_handler.get_total_n_samples()
            ten_minutes_samples = 10 * 60 * self.eeginfo.sample_rate

            if total_samples <= ten_minutes_samples:
                start_idx_max = max(0, end_idx - (total_samples // self.epoch_length) * self.epoch_length)
            else:
                start_idx_max = end_idx - ten_minutes_samples
                start_idx_max = (start_idx_max // self.epoch_length) * self.epoch_length
            if single_epoch:
                start_idx_max = start_idx

            epoch_data = self.db_handler.retrieve_data(start_idx_max, end_idx)
            self.make_mne_object(epoch_data, self.eeginfo.sample_rate)
            return start_idx_max
        except Exception as e:
            self.logger.error(f'Analyzer: Failed to maximize analysis epoch: {e}', exc_info=True)
            return None

    def run(self):

        self.eeginfo = self.db_handler.retrieve_info()

        while True:
            start_idx, end_idx, start_time = self.db_handler.find_next_epoch_indices(len(self.analysis_results), self.epoch_length)

            if start_idx is not None:
                if self.mode == 'U-Sleep':
                    self.maximize_analysis_epoch(start_idx, end_idx)
                    analysis_result = self.analyze_epoch_usleep_scorer(start_time)
                elif self.mode == 'YASA':
                    self.maximize_analysis_epoch(start_idx, end_idx)
                    analysis_result = self.analyze_epoch_yasa_scorer(start_time)
                elif self.mode == 'yasa_analyzer':
                    self.maximize_analysis_epoch(start_idx, end_idx, single_epoch=True)
                    analysis_result = self.analyze_epoch_yasa(start_time)
                else:
                    self.logger.error(f'Analyzer: Unknown mode: {self.mode}', exc_info=True)
                    analysis_result = None
                if analysis_result is not None:
                    self.analysis_results.append(analysis_result)
            time.sleep(0.1)
